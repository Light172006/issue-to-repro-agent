from repro.agent import run_agent
from repro.llm import Budget, FakeProvider
from repro.parser import IssueRecord


class Toolbox:
    def __init__(self):
        self.calls = []
        self.closed = False

    def execute(self, name, args):
        self.calls.append((name, args))
        return {'output': 'stopped', 'outcome': 'gave_up'}

    def close(self):
        self.closed = True


def test_give_up_via_budgeted_fake_provider(tmp_path):
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider(message=[{'type': 'function_call', 'name': 'give_up',
                                      'arguments': '{"reason":"not found"}', 'call_id': '1'}])
    toolbox = Toolbox()
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), toolbox,
                           provider=provider, budget=budget, model_config=config,
                           model='fake', trace_path=str(tmp_path / 'trace.jsonl'),
                           tool_schemas=[])
    finally:
        budget.close()
    assert result.outcome == 'gave_up'
    assert result.steps == 1
    assert toolbox.calls == [('give_up', {'reason': 'not found'})]
    assert toolbox.closed


def test_no_tool_calls_cannot_claim_success(tmp_path):
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider(message='I reproduced it')
    toolbox = Toolbox()
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), toolbox,
                           provider=provider, budget=budget, model_config=config,
                           model='fake', trace_path=str(tmp_path / 'trace.jsonl'),
                           tool_schemas=[])
    finally:
        budget.close()
    assert result.outcome == 'error'
    assert result.steps == 2
    assert toolbox.calls == []
    assert toolbox.closed
