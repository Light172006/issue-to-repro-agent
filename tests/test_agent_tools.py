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
