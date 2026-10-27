import json
import tempfile
import unittest
from pathlib import Path

from repro.llm import Budget, BudgetExceeded, FakeProvider, UsageUnavailable, call_model, cost_nanos

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

if __name__ == '__main__': unittest.main()
