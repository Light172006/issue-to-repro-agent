from typer.testing import CliRunner

from repro.cli import app


def test_help_and_missing_argument_do_not_start_pipeline():
    runner = CliRunner()
    assert runner.invoke(app, ['--help']).exit_code == 0
    assert runner.invoke(app, []).exit_code == 2


def test_parser_fallback_never_starts_environment_build(tmp_path, monkeypatch):
    import json
    from unittest.mock import Mock

    from repro import cli
    from repro.parser import IssueRecord

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('META_MODEL_API_KEY', 'fake-key-for-offline-test')
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}

    def config(path):
        if path.name == 'limits.yaml':
            return limits
        if path.name == 'parser.yaml':
            return {'default_model': 'fake'}
        return {'fake': {'input_per_million': '1.25', 'output_per_million': '4.25'}}

    def invalid_parser(issue, model):
        model.trace_path.write_text(json.dumps({'event': 'parser_result', 'fallback': True}) + '\n')
        return IssueRecord(repo='fictional/mapping', issue=1)

    docker_start = Mock()
    provider = Mock()
    monkeypatch.setattr(cli, 'load_config', config)
    monkeypatch.setattr(cli, 'OpenAIProvider', Mock(return_value=provider))
    monkeypatch.setattr(cli, 'fetch_issue', Mock(return_value=({'repo': 'fictional/mapping', 'number': 1}, None)))
    monkeypatch.setattr(cli, 'parse_issue', invalid_parser)
    monkeypatch.setattr(cli.docker, 'from_env', docker_start)
    result = CliRunner().invoke(app, ['https://github.com/fictional/mapping/issues/1'])
    assert result.exit_code == 1
    assert 'Parser output failed validation; environment was not built' in result.output
    docker_start.assert_not_called()
    provider.close.assert_called_once()
    saved = list((tmp_path / 'runs').glob('*/result.json'))
    assert len(saved) == 1
    assert json.loads(saved[0].read_text())['outcome'] == 'error'


def test_reported_markdown_version_reaches_environment_builder(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    from unittest.mock import MagicMock, Mock

    from repro import cli
    from repro.agent import AgentResult

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('META_MODEL_API_KEY', 'fake-key-for-offline-test')
    limits = {'max_steps': 25, 'max_run_usd': 1, 'max_seconds': 900,
              'max_daily_usd': 5, 'max_total_usd': 120}

    def config(path):
        if path.name == 'limits.yaml':
            return limits
        if path.name == 'parser.yaml':
            return {'default_model': 'fake'}
        return {'fake': {'input_per_million': '1.25', 'output_per_million': '4.25'}}

    class OfflineParser:
        def __init__(self, provider, budget, models, trace_path, model):
            self.trace_path = trace_path

        def __call__(self, messages, schema):
            data = {'version': None, 'last_good_version': None, 'python': None, 'os': None,
                    'steps': [], 'expected': None, 'actual': None,
                    'symptom': {'kind': 'other', 'type': None, 'signature': None}, 'missing': []}
            return SimpleNamespace(message=json.dumps(data))

    issue = {'repo': 'fictional/mapping', 'number': 1,
             'body': '* Python `3.11.3`\n* Version `2.7.1`\n'}
    builder = Mock()
    builder.build.return_value = {'image': 'fake-image', 'selected_ref': '2.7.1',
                                  'commit': 'a' * 40}
    monkeypatch.setattr(cli, 'load_config', config)
    monkeypatch.setattr(cli, 'OpenAIProvider', Mock(return_value=Mock()))
    monkeypatch.setattr(cli, 'ModelClient', OfflineParser)
    monkeypatch.setattr(cli, 'fetch_issue', Mock(return_value=(issue, None)))
    monkeypatch.setattr(cli.docker, 'from_env', Mock(return_value=Mock()))
    monkeypatch.setattr(cli.httpx, 'Client', MagicMock())
    monkeypatch.setattr(cli, 'EnvironmentBuilder', Mock(return_value=builder))
    monkeypatch.setattr(cli, 'Sandbox', Mock())
    monkeypatch.setattr(cli, 'SandboxTools', Mock())
    monkeypatch.setattr(cli, 'run_agent', Mock(return_value=AgentResult('gave_up', None, None, 0, '0', 0)))
    result = CliRunner().invoke(app, ['https://github.com/fictional/mapping/issues/1'])
    assert result.exit_code == 0, result.exception
    assert 'Parsed version: 2.7.1' in result.output
    assert 'Environment ref: 2.7.1' in result.output
    assert builder.build.call_args.args[:2] == ('fictional/mapping', '2.7.1')
    assert cli.run_agent.call_args.args[0].version == '2.7.1'
