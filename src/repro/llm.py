"""Budget-aware model calls. No API key or prompt content is written to the trace."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


class BudgetExceeded(RuntimeError):
    """A configured limit prevents the request."""


class UsageUnavailable(RuntimeError):
    """Usage was unavailable; the reservation remains charged conservatively."""


@dataclass(frozen=True)
class Reply:
    message: Any
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class Budget:
    """Single-threaded run state plus a shared SQLite reservation ledger.

    All monetary values in the ledger are integer nanodollars. Reservations are
    intentionally not released if a request fails or returns invalid usage.
    """
    def __init__(self, ledger: str | Path, limits: dict, clock: Callable = time.monotonic):
        self.limits = limits
        self.clock = clock
        self.started = clock()
        self.steps = 0
        self.run_charged = 0
        self.db = sqlite3.connect(str(ledger), timeout=30)
        self.db.execute('CREATE TABLE IF NOT EXISTS charges (day TEXT NOT NULL, amount INTEGER NOT NULL)')
        self.db.commit()

    def close(self):
        self.db.close()

    def reserve(self, amount: int) -> None:
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
            self.db.execute('INSERT INTO charges VALUES (?, ?)', (day, amount))
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        self.steps += 1
        self.run_charged += amount


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


class FakeProvider:
    def __init__(self, message='fake reply', input_tokens=10, output_tokens=5):
        self.message = message
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.calls = 0

    def complete(self, *, model, messages, tools, max_output_tokens, timeout):
        self.calls += 1
        return self.message, self.input_tokens, self.output_tokens


class OpenAIProvider:
    def __init__(self, *, base_url: str, api_key: str):
        if not base_url or not api_key:
            raise ValueError('Explicit API base URL and API key are required')
        from openai import OpenAI
        self.client = OpenAI(base_url=base_url, api_key=api_key, max_retries=0)

    def complete(self, *, model, messages, tools, max_output_tokens, timeout):
        params = dict(model=model, messages=messages, max_tokens=max_output_tokens, timeout=timeout)
        if tools:
            params.update(tools=tools, tool_choice='auto', parallel_tool_calls=False)
        response = self.client.chat.completions.create(**params)
        if not response.usage or not response.choices:
            raise UsageUnavailable('Provider did not return usage and a response')
        return response.choices[0].message, response.usage.prompt_tokens, response.usage.completion_tokens


def call_model(*, provider, model: str, messages: list, tools: list | None,
               budget: Budget, model_config: dict, trace_path: str | Path,
               max_output_tokens: int = 256) -> Reply:
    """Make one call. Reserve its maximum possible charge before sending.

    `input_token_ceiling` must be an independently verified upper bound on the
    provider's prompt usage, including tool schemas and server-added tokens.
    Real providers are disabled unless that guarantee is configured.
    """
    cfg = model_config[model]
    if max_output_tokens <= 0:
        raise ValueError('max_output_tokens must be positive')
    ceiling = int(cfg['input_token_ceiling'])
    if ceiling <= 0:
        raise ValueError('input_token_ceiling must be positive')
    # No generic OpenAI-compatible API enforces a prompt-token ceiling. Fail
    # closed for real calls until an enforceable provider contract exists.
    if isinstance(provider, OpenAIProvider):
        raise BudgetExceeded('Real provider disabled: prompt-token ceiling cannot be enforced before billing')
    reserve = cost_nanos(ceiling, max_output_tokens, cfg)
    budget.reserve(reserve)
    remaining = float(budget.limits['max_seconds']) - (budget.clock() - budget.started)
    if remaining <= 0:
        raise BudgetExceeded('Time limit reached before request')
    try:
        message, inp, out = provider.complete(model=model, messages=messages, tools=tools,
                                              max_output_tokens=max_output_tokens, timeout=remaining)
        if type(inp) is not int or type(out) is not int or inp < 0 or out < 0 or inp > ceiling or out > max_output_tokens:
            raise UsageUnavailable('Usage missing, invalid, or exceeds reservation')
        actual = cost_nanos(inp, out, cfg)
        # Keep reservation in the ledger, including for successful calls: this
        # is conservative and keeps run, daily and total caps safe across calls.
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
