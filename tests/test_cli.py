from typer.testing import CliRunner

from repro.cli import app


def test_help_and_missing_argument_do_not_start_pipeline():
    runner = CliRunner()
    assert runner.invoke(app, ['--help']).exit_code == 0
    assert runner.invoke(app, []).exit_code == 2
