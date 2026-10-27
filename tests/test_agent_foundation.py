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


def test_only_harness_confirmed_submit_ends_as_candidate(tmp_path):
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider()
    replies = iter([
        [{'type': 'function_call', 'name': 'submit_repro',
          'arguments': '{"path":"/work/repro/test_bug.py"}', 'call_id': '1'}],
        [{'type': 'function_call', 'name': 'submit_repro',
          'arguments': '{"path":"/work/repro/test_bug.py"}', 'call_id': '2'}],
    ])
    provider.complete = lambda **kwargs: (next(replies), 10, 5)

    class CheckingToolbox(Toolbox):
        def execute(self, name, args):
            self.calls.append((name, args))
            if len(self.calls) == 1:
                return {'output': 'Symptom not matched'}
            return {'output': 'confirmed', 'outcome': 'candidate_found',
                    'path': args['path'], 'verdict': 'exact'}

    toolbox = CheckingToolbox()
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), toolbox,
                           provider=provider, budget=budget, model_config=config,
                           model='fake', trace_path=str(tmp_path / 'trace.jsonl'),
                           tool_schemas=[])
    finally:
        budget.close()
    assert result.outcome == 'candidate_found'
    assert result.verdict == 'exact'
    assert result.steps == 2
    assert len(toolbox.calls) == 2
    assert toolbox.closed


def test_multiple_tool_calls_executes_only_first(tmp_path):
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider(message=[
        {'type': 'function_call', 'name': 'give_up', 'arguments': '{"reason":"done"}', 'call_id': '1'},
        {'type': 'function_call', 'name': 'write_file', 'arguments': '{}', 'call_id': '2'},
    ])
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
    assert toolbox.calls == [('give_up', {'reason': 'done'})]


def test_repeated_tool_errors_mark_stall_and_stop_at_step_limit(tmp_path):
    limits = {'max_steps': 3, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider(message=[{'type': 'function_call', 'name': 'unknown',
                                      'arguments': '{}', 'call_id': '1'}])

    class ErrorToolbox(Toolbox):
        def execute(self, name, args):
            self.calls.append((name, args))
            return {'output': 'Error: unknown tool'}

    toolbox = ErrorToolbox()
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), toolbox,
                           provider=provider, budget=budget, model_config=config,
                           model='fake', trace_path=str(tmp_path / 'trace.jsonl'),
                           tool_schemas=[])
    finally:
        budget.close()
    assert result.outcome == 'limit_hit:steps'
    assert result.stalled
    assert result.steps == 3
    assert toolbox.closed


def test_malformed_arguments_are_recoverable(tmp_path):
    limits = {'max_steps': 2, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider(message=[{'type': 'function_call', 'name': 'run_shell',
                                      'arguments': '{oops', 'call_id': '1'}])
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
    assert result.outcome == 'limit_hit:steps'
    assert not toolbox.calls
    assert toolbox.closed


def test_dollar_limit_stops_before_fake_provider_call(tmp_path):
    limits = {'max_steps': 25, 'max_run_usd': '0.000000001', 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider()
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
    assert result.outcome == 'limit_hit:dollars'
    assert provider.calls == 0
    assert toolbox.closed


def test_time_limit_stops_before_call(tmp_path):
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider()
    toolbox = Toolbox()
    times = iter((0.0, 901.0, 902.0))
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), toolbox,
                           provider=provider, budget=budget, model_config=config,
                           model='fake', trace_path=str(tmp_path / 'trace.jsonl'),
                           tool_schemas=[], clock=lambda: next(times))
    finally:
        budget.close()
    assert result.outcome == 'limit_hit:time'
    assert provider.calls == 0
    assert toolbox.closed


def test_agent_uses_minimal_reasoning_and_records_output_limit(tmp_path):
    import json

    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    provider = FakeProvider(message=[], output_tokens=2048)
    options = []
    complete = provider.complete

    def capture(**kwargs):
        options.append(kwargs)
        return complete(**kwargs)

    provider.complete = capture
    toolbox = Toolbox()
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    trace_path = tmp_path / 'trace.jsonl'
    try:
        result = run_agent(IssueRecord(repo='example/project', issue=1), toolbox,
                           provider=provider, budget=budget, model_config=config,
                           model='fake', trace_path=str(trace_path), tool_schemas=[])
    finally:
        budget.close()
    assert result.outcome == 'error'
    assert all(call['reasoning_effort'] == 'minimal' for call in options)
    assert all(call['max_output_tokens'] == 2048 for call in options)
    events = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert events[0]['error'] == 'No tool call; output token limit reached'
    assert events[-1]['outcome'] == 'error'
