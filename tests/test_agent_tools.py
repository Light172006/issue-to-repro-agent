from unittest.mock import Mock

from repro.parser import IssueRecord, Symptom
from repro.sandbox import SandboxResult
from repro.tools import SandboxTools


def make_tools():
    sandbox = Mock()
    sandbox.run.return_value = SandboxResult(0, 'ok', False)
    issue = IssueRecord(repo='example/library', issue=1,
                        symptom=Symptom(kind='exception', type='ValueError',
                                        signature='ValueError: broken @ file.py:parse'))
    return SandboxTools(sandbox, issue), sandbox


def test_path_traversal_rejected_before_container():
    tools, sandbox = make_tools()
    result = tools.execute('write_file', {'path': '../outside', 'content': 'x'})
    assert 'traversal' in result['output']
    sandbox.run.assert_not_called()


def test_submit_requires_failed_test_and_matching_symptom():
    tools, sandbox = make_tools()
    sandbox.run.side_effect = [SandboxResult(0, '', False),
                               SandboxResult(1, 'File "file.py", line 3, in parse\nValueError: broken', False)]
    result = tools.execute('submit_repro', {'path': '/work/repro/test_bug.py'})
    assert result['outcome'] == 'candidate_found'
    assert result['verdict'] == 'exact'
    assert sandbox.run.call_count == 2


def test_passing_test_cannot_be_candidate():
    tools, sandbox = make_tools()
    sandbox.run.return_value = SandboxResult(0, 'ValueError in parse', False)
    assert 'outcome' not in tools.execute('submit_repro', {'path': '/work/repro/test_bug.py'})


def test_network_install_command_rejected():
    tools, sandbox = make_tools()
    assert 'already' in tools.execute('run_shell', {'command': 'pip install foo'})['output']
    sandbox.run.assert_not_called()


def test_absolute_write_outside_repro_is_rejected():
    tools, sandbox = make_tools()
    for path in ('/var/tmp/repro/source/library.py', '/etc/passwd', '/tmp/test.py'):
        result = tools.execute('write_file', {'path': path, 'content': 'x'})
        assert 'outside allowed' in result['output']
    sandbox.run.assert_not_called()


def test_read_range_zero_is_rejected():
    tools, sandbox = make_tools()
    result = tools.execute('read_file', {'path': 'test.py', 'start_line': 0})
    assert 'Invalid line range' in result['output']
    sandbox.run.assert_not_called()


def test_scripted_fake_model_reaches_harness_confirmation(tmp_path):
    from repro.agent import run_agent
    from repro.llm import Budget, FakeProvider

    tools, sandbox = make_tools()
    sandbox.run.side_effect = [SandboxResult(0, '', False),
                               SandboxResult(1, 'File "file.py", line 3, in parse\nValueError: broken', False)]
    provider = FakeProvider(message=[{'type': 'function_call', 'name': 'submit_repro',
                                      'arguments': '{"path":"/work/repro/test_bug.py"}', 'call_id': '1'}])
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    config = {'fake': {'input_token_ceiling': 1000, 'input_per_million': '1.25',
                       'output_per_million': '4.25'}}
    budget = Budget(tmp_path / 'ledger.sqlite', limits)
    try:
        result = run_agent(tools.issue, tools, provider=provider, budget=budget,
                           model_config=config, model='fake',
                           trace_path=str(tmp_path / 'trace.jsonl'), tool_schemas=[])
    finally:
        budget.close()
    assert result.outcome == 'candidate_found'
    assert result.verdict == 'exact'
    assert sandbox.run.call_count == 2
    sandbox.close.assert_called_once()
