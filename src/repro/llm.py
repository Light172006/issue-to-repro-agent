"""Budget-aware model calls. No API key or prompt content is written to the trace."""
from __future__ import annotations

import json
import sqlite3
import time
import threading
from functools import wraps
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


class BudgetExceeded(RuntimeError):
    """A configured limit prevents the request."""


class ProviderError(RuntimeError):
    """A provider request failed without exposing response or request secrets."""


class UsageUnavailable(RuntimeError):
    """Usage was unavailable; the reservation remains charged conservatively."""


@dataclass(frozen=True)
class Reply:
    message: Any
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


def synchronized(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapper


class Budget:
    """Thread-safe run state plus a shared SQLite reservation ledger.

    All monetary values in the ledger are integer nanodollars. Reservations are
    intentionally not released if a request fails or returns invalid usage.
    """
    def __init__(self, ledger: str | Path, limits: dict, clock: Callable = time.monotonic):
        ceilings = {'max_steps': 25, 'max_run_usd': Decimal('1'),
                    'max_seconds': 900, 'max_daily_usd': Decimal('5'),
                    'max_total_usd': Decimal('120')}
        for key, maximum in ceilings.items():
            value = Decimal(str(limits[key]))
            if not value.is_finite() or value <= 0 or value > maximum:
                raise ValueError(f'{key} must be positive and at most {maximum}')
        if Decimal(str(limits['max_steps'])) != int(limits['max_steps']):
            raise ValueError('max_steps must be an integer')
        self._lock = threading.RLock()
        self.limits = dict(limits)
        self.clock = clock
        self.started = clock()
        self.steps = 0
        self.run_charged = 0
        self._breached = False
        self.db = sqlite3.connect(str(ledger), timeout=30, check_same_thread=False)
        self.db.execute('CREATE TABLE IF NOT EXISTS charges (day TEXT NOT NULL, amount INTEGER NOT NULL)')
        self.db.commit()

    @synchronized
    def close(self):
        self.db.close()

    @synchronized
    def reserve(self, amount: int) -> int:
        if self._breached:
            raise BudgetExceeded('Run stopped after usage exceeded its reservation')
        if self.steps >= int(self.limits['max_steps']):
            raise BudgetExceeded('Step limit reached')
        if self.clock() - self.started >= float(self.limits['max_seconds']):
            raise BudgetExceeded('Time limit reached')
        if self.run_charged + amount > dollars(self.limits['max_run_usd']):
            raise BudgetExceeded('Run budget would be exceeded')
        day = time.strftime('%Y-%m-%d', time.gmtime())
        try:
            self.db.execute('BEGIN IMMEDIATE')
            total = self.db.execute('SELECT COALESCE(SUM(amount), 0) FROM charges').fetchone()[0]
            daily = self.db.execute('SELECT COALESCE(SUM(amount), 0) FROM charges WHERE day = ?', (day,)).fetchone()[0]
            if total + amount > dollars(self.limits['max_total_usd']):
                raise BudgetExceeded('Total budget would be exceeded')
            if daily + amount > dollars(self.limits['max_daily_usd']):
                raise BudgetExceeded('Daily budget would be exceeded')
            cursor = self.db.execute('INSERT INTO charges VALUES (?, ?)', (day, amount))
            reservation_id = cursor.lastrowid
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.steps += 1
        self.run_charged += amount
        return reservation_id

    @synchronized
    def reconcile(self, reservation_id: int, reserved: int, actual: int) -> None:
        if actual > reserved or actual < 0:
            raise UsageUnavailable('Actual charge exceeds reservation')
        with self.db:
            cursor = self.db.execute('UPDATE charges SET amount = ? WHERE rowid = ? AND amount = ?',
                                     (actual, reservation_id, reserved))
            if cursor.rowcount != 1:
                raise UsageUnavailable('Reservation could not be reconciled')
        self.run_charged -= reserved - actual

    @synchronized
    def record_overrun(self, reservation_id: int, reserved: int, actual: int) -> None:
        # Once billed, never record less than known actual usage. Stop this run.
        charged = max(reserved, actual)
        with self.db:
            cursor = self.db.execute('UPDATE charges SET amount = ? WHERE rowid = ? AND amount = ?',
                                     (charged, reservation_id, reserved))
            if cursor.rowcount != 1:
                raise UsageUnavailable('Reservation could not be updated')
        self.run_charged += charged - reserved
        self._breached = True


def dollars(value: str | int) -> int:
    return int(Decimal(str(value)) * 1_000_000_000)


def cost_nanos(input_tokens: int, output_tokens: int, prices: dict) -> int:
    # Prices are dollars per million tokens; round upwards to preserve the cap.
    amount = (Decimal(input_tokens) * Decimal(str(prices['input_per_million'])) +
              Decimal(output_tokens) * Decimal(str(prices['output_per_million']))) * 1000
    return int(amount.to_integral_value(rounding='ROUND_CEILING'))


def load_config(path: str | Path) -> dict:
    # JSON is a YAML 1.2 subset. This avoids an extra YAML runtime dependency.
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _valid_messages(messages: object, *, allow_tools: bool) -> bool:
    """Accept text and paired local function calls, never hosted tool actions."""
    if not isinstance(messages, list):
        return False
    pending = None
    for item in messages:
        if not isinstance(item, dict):
            return False
        if set(item) == {'role', 'content'}:
            if pending is not None or item['role'] not in ('system', 'developer', 'user', 'assistant'):
                return False
            if not isinstance(item['content'], str):
                return False
        elif allow_tools and set(item) == {'type', 'call_id', 'name', 'arguments'}:
            if (pending is not None or item['type'] != 'function_call' or
                    any(not isinstance(item[k], str) or not item[k] for k in ('call_id', 'name')) or
                    not isinstance(item['arguments'], str)):
                return False
            pending = item['call_id']
        elif allow_tools and set(item) == {'type', 'call_id', 'output'}:
            if (item['type'] != 'function_call_output' or pending is None or
                    item['call_id'] != pending or not isinstance(item['output'], str)):
                return False
            pending = None
        else:
            return False
    return pending is None


class FakeProvider:
    def __init__(self, message='fake reply', input_tokens=10, output_tokens=5):
        self.message = message
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls = 0

    def complete(self, *, model, messages, tools, max_output_tokens, timeout, temperature=None, json_schema=None, reasoning_effort=None):
        self.calls += 1
        return self.message, self.input_tokens, self.output_tokens


class OpenAIProvider:
    """Meta Responses adapter: count and generate the same immutable input."""
    def __init__(self, *, api_key: str, base_url: str = 'https://api.meta.ai/v1'):
        if base_url.rstrip('/') != 'https://api.meta.ai/v1' or not api_key:
            raise ValueError('Meta API URL and API key are required')
        import httpx
        from openai import OpenAI
        self.http = httpx.Client(base_url=base_url.rstrip('/'),
                                 headers={'Authorization': f'Bearer {api_key}'}, timeout=30)
        self.client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0)

    def count(self, *, model, messages, tools, timeout, temperature=None, json_schema=None, reasoning_effort=None):
        body = {'model': model, 'input': messages}
        if tools:
            body['tools'] = tools
            body['parallel_tool_calls'] = False
        if temperature is not None:
            body['temperature'] = temperature
        if reasoning_effort is not None:
            body['reasoning'] = {'effort': reasoning_effort}
        if json_schema is not None:
            body['text'] = {'format': {'type': 'json_schema', 'name': 'issue_record', 'schema': json_schema, 'strict': True}}
        response = self.http.post('responses/input_tokens', json=body, timeout=timeout)
        response.raise_for_status()
        count = response.json()['input_tokens']
        if type(count) is not int or count < 0:
            raise UsageUnavailable('Invalid preflight token count')
        return count

    def complete(self, *, model, messages, tools, max_output_tokens, timeout, temperature=None, json_schema=None, reasoning_effort=None):
        params = dict(model=model, input=messages, max_output_tokens=max_output_tokens,
                      timeout=timeout, store=False)
        if tools:
            params.update(tools=tools, parallel_tool_calls=False)
        if temperature is not None:
            params['temperature'] = temperature
        if reasoning_effort is not None:
            params['reasoning'] = {'effort': reasoning_effort}
        if json_schema is not None:
            params['text'] = {'format': {'type': 'json_schema', 'name': 'issue_record', 'schema': json_schema, 'strict': True}}
        response = self.client.responses.create(**params)
        if response.usage is None:
            raise UsageUnavailable('Provider did not return usage')
        return response.output, response.usage.input_tokens, response.usage.output_tokens

    def close(self):
        self.http.close()
        self.client.close()


def call_model(*, provider, model: str, messages: list, tools: list | None,
               budget: Budget, model_config: dict, trace_path: str | Path,
               max_output_tokens: int = 256, temperature: float | None = None, json_schema: dict | None = None,
               reasoning_effort: str | None = None) -> Reply:
    """Make one call. Reserve its maximum possible charge before sending.

    Real calls use Meta's preflight count plus a safety margin and bounded output.
    The bound assumes stable provider tokenization and documented billing.
    """
    if model not in model_config:
        raise ValueError(f'Unknown model: {model!r}')
    cfg = model_config[model]
    for key in ('input_per_million', 'output_per_million'):
        price = Decimal(str(cfg[key]))
        if not price.is_finite() or price < 0:
            raise ValueError('Prices must be finite and non-negative')
    if type(max_output_tokens) is not int or max_output_tokens <= 0:
        raise ValueError('max_output_tokens must be positive')
    # Snapshot once: the count and generation must receive identical inputs.
    messages = json.loads(json.dumps(messages))
    tools = json.loads(json.dumps(tools)) if tools else None
    if type(provider) is OpenAIProvider:
        minimum_prices = {'muse-spark-1.3': (Decimal('1.25'), Decimal('4.25')),
                          'muse-wonder-1.0': (Decimal('4'), Decimal('20'))}
        if model not in minimum_prices:
            raise ValueError('Only configured Meta text models are supported')
        if (Decimal(str(cfg['input_per_million'])) < minimum_prices[model][0] or
                Decimal(str(cfg['output_per_million'])) < minimum_prices[model][1]):
            raise ValueError('Configured price is below the verified standard rate')
        if not _valid_messages(messages, allow_tools=bool(tools)):
            raise ValueError('Invalid text messages or local function-call history')
        if tools and any(not isinstance(t, dict) or t.get('type') != 'function' for t in tools):
            raise ValueError('Only local function tools are allowed')
        if budget.steps >= int(budget.limits['max_steps']):
            raise BudgetExceeded('Step limit reached')
        remaining = float(budget.limits['max_seconds']) - (budget.clock() - budget.started)
        if remaining <= 0:
            raise BudgetExceeded('Time limit reached')
        try:
            count_options = {}
            if temperature is not None:
                count_options['temperature'] = temperature
            if json_schema is not None:
                count_options['json_schema'] = json_schema
            if reasoning_effort is not None:
                count_options['reasoning_effort'] = reasoning_effort
            count = provider.count(model=model, messages=messages, tools=tools, timeout=min(30, remaining), **count_options)
        except Exception:
            raise ProviderError('Provider token-count request failed') from None
        ceiling = count + max(128, (count + 99) // 100)
    elif type(provider) is FakeProvider:
        ceiling = int(cfg['input_token_ceiling'])
    else:
        raise ValueError('Unrecognized provider; no billing contract available')
    if ceiling <= 0:
        raise ValueError('input_token_ceiling must be positive')
    reserve = cost_nanos(ceiling, max_output_tokens, cfg)
    reservation_id = budget.reserve(reserve)
    remaining = float(budget.limits['max_seconds']) - (budget.clock() - budget.started)
    if remaining <= 0:
        raise BudgetExceeded('Time limit reached before request')
    try:
        try:
            options = {}
            if temperature is not None:
                options['temperature'] = temperature
            if json_schema is not None:
                options['json_schema'] = json_schema
            if reasoning_effort is not None:
                options['reasoning_effort'] = reasoning_effort
            message, inp, out = provider.complete(model=model, messages=messages, tools=tools,
                                                  max_output_tokens=max_output_tokens, timeout=remaining, **options)
        except Exception:
            raise ProviderError('Provider generation request failed; reservation retained') from None
        if type(inp) is not int or type(out) is not int or inp < 0 or out < 0:
            raise UsageUnavailable('Provider returned missing or invalid token usage; reservation retained')
        actual = cost_nanos(inp, out, cfg)
        if inp > ceiling or out > max_output_tokens or actual > reserve:
            budget.record_overrun(reservation_id, reserve, actual)
            with open(trace_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps({'event': 'usage_exceeded_reservation', 'input_tokens': inp,
                                    'input_ceiling': ceiling, 'output_tokens': out,
                                    'output_ceiling': max_output_tokens,
                                    'actual_cost_usd': str(Decimal(actual) / Decimal(1_000_000_000))}) + '\n')
            raise UsageUnavailable(f'Usage exceeded reservation: input={inp}/{ceiling}, '
                                   f'output={out}/{max_output_tokens}; run stopped')
        budget.reconcile(reservation_id, reserve, actual)
        result = Reply(message, inp, out, Decimal(actual) / Decimal(1_000_000_000))
        event = {'event': 'model_call', 'model': model, 'input_tokens': inp,
                 'output_tokens': out, 'cost_usd': str(result.cost_usd),
                 'reserved_usd': str(Decimal(reserve) / Decimal(1_000_000_000)),
                 'step': budget.steps}
        with open(trace_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event) + '\n')
        if budget.clock() - budget.started >= float(budget.limits['max_seconds']):
            raise BudgetExceeded('Time limit reached during request')
        return result
    except Exception:
        # Never log exception text, credentials, issue text or response content.
        with open(trace_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps({'event': 'model_call_failed', 'model': model,
                                'step': budget.steps, 'reservation_retained': True}) + '\n')
        raise

