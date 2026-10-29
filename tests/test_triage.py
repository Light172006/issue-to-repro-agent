import pytest

from repro.parser import IssueRecord
from repro.triage import assess


def issue(body):
    return {'body': body, 'reporter': 'alice', 'comments': []}


def test_hardware_bound_issue_is_not_feasible():
    record = IssueRecord(repo='a/b', issue=1)
    result = assess(issue('Reproduction requires a GPU.'), record)
    assert result.status == 'not_feasible'
    assert 'GPU' in result.reason


@pytest.mark.parametrize('body', ['A GPU is available but not needed.', 'This does not require a GPU.',
                                  'No network access is required.'])
def test_mention_or_negation_does_not_prove_requirement(body):
    assert assess(issue(body), IssueRecord(repo='a/b', issue=1)) is None


def test_vague_issue_gets_specific_questions():
    record = IssueRecord(repo='a/b', issue=1,
        missing=['steps', 'actual behavior', 'minimal code', 'python version'])
    result = assess(issue('It does not work.'), record)
    assert result.status == 'needs_info'
    assert any('Python version' in question for question in result.questions)
    assert any('steps' in question for question in result.questions)
    assert any('code' in question for question in result.questions)


def test_maintainer_comment_does_not_trigger_feasibility():
    data = issue('A normal issue.')
    data['comments'] = [{'author': 'maintainer', 'body': 'requires a GPU'}]
    assert assess(data, IssueRecord(repo='a/b', issue=1)) is None


@pytest.mark.parametrize(('body', 'missing', 'expected'), [
    ('The reproducer requires a GPU.', [], 'not_feasible'),
    ('Something is broken.', ['steps', 'actual behavior', 'minimal code'], 'needs_info'),
])
def test_cli_stops_early_and_writes_draft(tmp_path, monkeypatch, body, missing, expected):
    import json
    from unittest.mock import Mock

    from typer.testing import CliRunner

    from repro import cli
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('META_MODEL_API_KEY', 'fake-key')
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}
    monkeypatch.setattr(cli, 'load_config', lambda path: limits if path.name == 'limits.yaml'
                        else {'default_model': 'fake'} if path.name == 'parser.yaml' else {})
    monkeypatch.setattr(cli, 'OpenAIProvider', Mock(return_value=Mock()))
    monkeypatch.setattr(cli, 'fetch_issue', lambda *args, **kwargs: (issue(body), None))
    monkeypatch.setattr(cli, 'ModelClient', Mock())
    monkeypatch.setattr(cli, 'parse_issue', lambda *args: IssueRecord(repo='a/b', issue=1, missing=missing))
    monkeypatch.setattr(cli, '_parser_fell_back', lambda path: False)
    docker = Mock(side_effect=AssertionError('Docker must not be started'))
    monkeypatch.setattr(cli.docker, 'from_env', docker)
    result = CliRunner().invoke(cli.app, ['https://github.com/a/b/issues/1'])
    assert result.exit_code == 0, result.output
    result_path = next((tmp_path / 'runs').glob('*/result.json'))
    assert json.loads(result_path.read_text())['status'] == expected
    assert (result_path.parent / 'comment.md').is_file()
    docker.assert_not_called()
