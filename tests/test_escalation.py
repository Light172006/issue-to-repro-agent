import json
from decimal import Decimal

from repro.agent import run_agent
from repro.llm import Budget, FakeProvider
from repro.parser import IssueRecord


def test_stall_escalates_and_wonder_submits(tmp_path):
    config = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900, 'max_daily_usd': 5,
              'max_total_usd': 120, 'stall': {'min_steps': 4, 'repeat_error_threshold': 3},
              'escalation': {'enabled': True, 'model': 'wonder', 'max_dollars': '.60',
                             'min_remaining_dollars': '.25', 'min_remaining_steps': 5}}
    prices = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25', 'output_per_million': '4.25'},
              'wonder': {'input_token_ceiling': 1000, 'input_per_million': '4', 'output_per_million': '20'}}
    provider = FakeProvider()
    seen = []
    def complete(**kwargs):
        seen.append(kwargs['model'])
        name = 'submit_repro' if kwargs['model'] == 'wonder' else 'run_shell'
        args = {'path': '/work/repro/test_x.py'} if name == 'submit_repro' else {'command': 'bad'}
        return ([{'type': 'function_call', 'name': name, 'arguments': json.dumps(args),
                  'call_id': str(len(seen))}], 10, 5)
    provider.complete = complete
    class Toolbox:
        def execute(self, name, args):
            if name == 'submit_repro':
                return {'output': 'confirmed', 'outcome': 'candidate_found', 'path': args['path'], 'verdict': 'exact'}
            return {'output': 'Error: repeated'}
        def close(self):
            pass
    budget = Budget(tmp_path / 'ledger', config)
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), Toolbox(), provider=provider,
                           budget=budget, model_config=prices, model='fake',
                           trace_path=str(tmp_path / 'trace'), tool_schemas=[])
    finally:
        budget.close()
    assert seen == ['fake'] * 4 + ['wonder']
    assert result.outcome == 'candidate_found'
    assert result.escalation['solved_after_escalation']
    assert Decimal(result.escalation['spark_cost']) + Decimal(result.escalation['wonder_cost']) == Decimal(result.cost_usd)
    events = [json.loads(line) for line in (tmp_path / 'trace').read_text().splitlines()]
    assert any(e.get('event') == 'escalation' for e in events)
    assert any(e.get('phase') == 'escalated' and e.get('model') == 'wonder' for e in events)


def test_wonder_error_falls_back_once_and_accounts_reservation(tmp_path):
    limits = {'max_steps': 10, 'max_run_usd': 1, 'max_seconds': 900, 'max_daily_usd': 5,
              'max_total_usd': 120, 'escalation': {'enabled': True, 'model': 'wonder',
              'max_dollars': '.60', 'min_remaining_dollars': '.25', 'min_remaining_steps': 5},
              'stall': {'min_steps': 4, 'repeat_error_threshold': 3}}
    rates = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25', 'output_per_million': '4.25'},
             'wonder': {'input_token_ceiling': 1000, 'input_per_million': '4', 'output_per_million': '20'}}
    provider = FakeProvider()
    seen = []
    def complete(**kwargs):
        seen.append(kwargs['model'])
        if kwargs['model'] == 'wonder':
            raise TimeoutError('private detail')
        name = 'give_up' if 'wonder' in seen else 'run_shell'
        return ([{'type': 'function_call', 'name': name, 'arguments': '{}', 'call_id': str(len(seen))}], 10, 5)
    provider.complete = complete
    class Toolbox:
        def execute(self, name, args):
            return {'output': 'done', 'outcome': 'gave_up'} if name == 'give_up' else {'output': 'Error: repeat'}
        def close(self):
            pass
    budget = Budget(tmp_path / 'ledger', limits)
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), Toolbox(), provider=provider,
                           budget=budget, model_config=rates, model='fake',
                           trace_path=str(tmp_path / 'trace'), tool_schemas=[])
    finally:
        budget.close()
    assert seen.count('wonder') == 1
    assert seen[-1] == 'fake'
    assert result.outcome == 'gave_up'
    assert result.escalation['failed_reason'] == 'ProviderError'
    assert Decimal(result.escalation['wonder_cost']) > 0
    assert Decimal(result.escalation['wonder_cost']) + Decimal(result.escalation['spark_cost']) == Decimal(result.cost_usd)
    assert 'private detail' not in (tmp_path / 'trace').read_text()


def test_wonder_worst_case_budget_blocks_generation(tmp_path):
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900, 'max_daily_usd': 5,
              'max_total_usd': 120, 'escalation': {'enabled': True, 'model': 'wonder',
              'max_dollars': '.00001', 'min_remaining_dollars': '.25', 'min_remaining_steps': 5},
              'stall': {'min_steps': 4, 'repeat_error_threshold': 3}}
    rates = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25', 'output_per_million': '4.25'},
             'wonder': {'input_token_ceiling': 1000, 'input_per_million': '4', 'output_per_million': '20'}}
    provider = FakeProvider(message=[{'type': 'function_call', 'name': 'run_shell',
                                      'arguments': '{"command":"bad"}', 'call_id': '1'}])
    seen = []
    original = provider.complete
    def complete(**kwargs):
        seen.append(kwargs['model'])
        return original(**kwargs)
    provider.complete = complete
    class Toolbox:
        def execute(self, name, args):
            return {'output': 'Error: repeat'}
        def close(self):
            pass
    budget = Budget(tmp_path / 'ledger', limits)
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), Toolbox(), provider=provider,
                           budget=budget, model_config=rates, model='fake',
                           trace_path=str(tmp_path / 'trace'), tool_schemas=[])
    finally:
        budget.close()
    assert result.outcome == 'limit_hit:dollars'
    assert 'wonder' not in seen
    assert Decimal(result.cost_usd) <= Decimal(1)
