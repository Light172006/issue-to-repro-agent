import json
import tempfile
import unittest
from pathlib import Path

from repro.llm import (
    Budget,
    BudgetExceeded,
    FakeProvider,
    UsageUnavailable,
    call_model,
)

LIMITS = {'max_steps': 2, 'max_run_usd': '1', 'max_seconds': 900, 'max_daily_usd': '5', 'max_total_usd': '120'}
MODELS = {'fake': {'input_per_million': '1.25', 'output_per_million': '4.25', 'input_token_ceiling': 1000}}

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.budget = Budget(self.root / 'ledger.sqlite3', LIMITS)
        self.provider = FakeProvider()

    def tearDown(self):
        self.budget.close()
        self.tmp.cleanup()

    def call(self):
        return call_model(provider=self.provider, model='fake', messages=[], tools=None, budget=self.budget,
                          model_config=MODELS, trace_path=self.root / 'trace.jsonl', max_output_tokens=20)

    def test_usage_cost_trace_and_limit(self):
        reply = self.call()
        self.assertEqual(str(reply.cost_usd), '0.00003375')
        self.assertEqual(json.loads((self.root / 'trace.jsonl').read_text())['input_tokens'], 10)
        self.call()
        with self.assertRaises(BudgetExceeded): self.call()
        self.assertEqual(self.provider.calls, 2)

    def test_budget_checked_before_call(self):
        self.budget.limits = {**LIMITS, 'max_run_usd': '0.000001'}
        with self.assertRaises(BudgetExceeded): self.call()
        self.assertEqual(self.provider.calls, 0)

    def test_expired_time_blocks_call(self):
        self.budget.started -= 901
        with self.assertRaises(BudgetExceeded): self.call()
        self.assertEqual(self.provider.calls, 0)

    def test_invalid_usage_retains_reservation(self):
        self.provider.input_tokens = 1001
        with self.assertRaises(UsageUnavailable): self.call()
        self.assertGreater(self.budget.run_charged, 0)

    def test_shared_total_limit(self):
        self.call()
        other = Budget(self.root / 'ledger.sqlite3', {**LIMITS, 'max_total_usd': '0.000001'})
        try:
            with self.assertRaises(BudgetExceeded):
                call_model(provider=self.provider, model='fake', messages=[], tools=None, budget=other,
                           model_config=MODELS, trace_path=self.root / 'other.jsonl')
        finally: other.close()


class MetaPreflightTests(ModelTests):
    def test_real_adapter_preflights_and_reconciles(self):
        from unittest.mock import Mock

        from repro.llm import OpenAIProvider
        provider = object.__new__(OpenAIProvider)
        provider.count = Mock(return_value=10)
        provider.complete = Mock(return_value=('hello', 10, 5))
        config = {'muse-spark-1.3': {'input_per_million': '1.25', 'output_per_million': '4.25'}}
        result = call_model(provider=provider, model='muse-spark-1.3', messages=[{'role':'user','content':'hello'}],
                            tools=None, budget=self.budget, model_config=config,
                            trace_path=self.root / 'trace.jsonl', max_output_tokens=20)
        self.assertEqual(provider.count.call_count, 1)
        self.assertEqual(provider.complete.call_count, 1)
        self.assertEqual(self.budget.run_charged, 33750)
        self.assertEqual(str(result.cost_usd), '0.00003375')

    def test_hosted_tools_rejected(self):
        from repro.llm import OpenAIProvider
        provider = object.__new__(OpenAIProvider)
        config = {'muse-spark-1.3': {'input_per_million': '1.25', 'output_per_million': '4.25'}}
        with self.assertRaises(ValueError):
            call_model(provider=provider, model='muse-spark-1.3', messages=[], tools=[{'type':'web_search'}],
                       budget=self.budget, model_config=config, trace_path=self.root / 'trace.jsonl')

    def test_cannot_raise_hard_limit(self):
        with self.assertRaises(ValueError): Budget(self.root / 'other.sqlite3', {**LIMITS, 'max_run_usd':'2'})

class EndpointTests(unittest.TestCase):
    def test_count_uses_exact_meta_url(self):
        import httpx

        from repro.llm import OpenAIProvider
        seen = []
        def handle(request):
            seen.append(str(request.url))
            return httpx.Response(200, json={'input_tokens': 12})
        provider = object.__new__(OpenAIProvider)
        provider.http = httpx.Client(base_url='https://api.meta.ai/v1', transport=httpx.MockTransport(handle))
        try:
            self.assertEqual(provider.count(model='muse-spark-1.3', messages=[], tools=None, timeout=5), 12)
        finally:
            provider.http.close()
        self.assertEqual(seen, ['https://api.meta.ai/v1/responses/input_tokens'])

if __name__ == '__main__': unittest.main()


def test_real_adapter_accepts_paired_local_tool_history(tmp_path):
    from unittest.mock import Mock

    from repro.llm import Budget, OpenAIProvider, call_model

    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = object.__new__(OpenAIProvider)
    provider.count = Mock(return_value=10)
    provider.complete = Mock(return_value=([], 10, 5))
    messages = [{'role': 'user', 'content': 'task'},
                {'type': 'function_call', 'call_id': 'call_1', 'name': 'run_shell', 'arguments': '{}'},
                {'type': 'function_call_output', 'call_id': 'call_1', 'output': 'ok'}]
    prices = {'muse-spark-1.3': {'input_per_million': '1.25', 'output_per_million': '4.25'}}
    try:
        call_model(provider=provider, model='muse-spark-1.3', messages=messages,
                   tools=[{'type': 'function'}], budget=budget, model_config=prices,
                   trace_path=tmp_path / 'trace')
    finally:
        budget.close()
    assert provider.count.call_args.kwargs['messages'] == messages
    assert provider.complete.call_args.kwargs['messages'] == messages


def test_tool_history_rejects_unpaired_or_hosted_actions():
    from repro.llm import _valid_messages

    call = {'type': 'function_call', 'call_id': 'call_1', 'name': 'run_shell', 'arguments': '{}'}
    output = {'type': 'function_call_output', 'call_id': 'call_1', 'output': 'ok'}
    assert _valid_messages([call, output], allow_tools=True)
    assert not _valid_messages([call], allow_tools=True)
    assert not _valid_messages([call, {**output, 'call_id': 'different'}], allow_tools=True)
    assert not _valid_messages([call, output], allow_tools=False)
    assert not _valid_messages([{'type': 'web_search_call', 'call_id': 'call_1'}], allow_tools=True)


def test_escalation_reservation_cap_blocks_before_provider_call(tmp_path):
    import pytest

    from repro.llm import Budget, BudgetExceeded, FakeProvider, call_model
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider()
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    try:
        with pytest.raises(BudgetExceeded, match='Escalation budget'):
            call_model(provider=provider, model='fake', messages=[], tools=None, budget=budget,
                       model_config=config, trace_path=tmp_path / 'trace', max_output_tokens=100,
                       max_reservation_nanos=1)
        assert provider.calls == 0 and budget.steps == 0 and budget.run_charged == 0
    finally:
        budget.close()
