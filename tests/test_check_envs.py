import json
from types import SimpleNamespace
from unittest.mock import Mock

from scripts.check_envs import baseline_recorded, compare_suite, parse_pytest, run_case


def test_pytest_summary_and_names():
    text = '''=========================== short test summary info ============================
FAILED tests/test_a.py::test_a - AssertionError
ERROR tests/test_b.py
================ 1 failed, 4 passed, 2 skipped, 1 error in 0.5s ================
'''
    parsed = parse_pytest(text)
    assert parsed['counts'] == {'passed': 4, 'failed': 1, 'skipped': 2, 'errors': 1}
    assert parsed['failure_names'] == ['tests/test_a.py::test_a', 'tests/test_b.py']
    assert compare_suite(parsed, {'passed': 4, 'failed': 1, 'skipped': 2}) == 'no (collection errors)'


def test_truncated_and_missing_summary_are_unknown():
    assert compare_suite(parse_pytest('partial'), {}) == 'unknown'
    assert compare_suite(parse_pytest('=== 1 passed in 0.1s ===', truncated=True), {}) == 'unknown'


def test_baseline_metadata_requires_explicit_failure_field():
    name = 'tests/test_a.py::test_a'
    assert baseline_recorded({'packages': [name]}, [name]) == 'NOT RECORDED'
    assert baseline_recorded({'baseline': {'failures': [{'test': name}]}}, [name]) == 'NOT RECORDED'
    assert baseline_recorded({'baseline': {'failures': [{'test': name, 'pre_existing': True}]}}, [name]) == 'yes'
    assert baseline_recorded({}, []) == 'not applicable'


def test_run_uses_production_builder_and_offline_sandbox(tmp_path, monkeypatch):
    from scripts import check_envs
    folder = tmp_path / 'case'
    folder.mkdir()
    (folder / 'environment.json').write_text(json.dumps({'commit': 'a' * 40}))
    builder = Mock()
    builder.build.return_value = {'image': 'sample', 'commit': 'a' * 40}
    result = SimpleNamespace(output='=== 2 passed, 1 failed in 1.0s ===\nFAILED tests/test_x.py::test_x - error\n',
                             original_length=90, timed_out=False, exit_code=1)
    sandbox = Mock()
    sandbox.__enter__ = Mock(return_value=sandbox)
    sandbox.__exit__ = Mock(return_value=None)
    sandbox.run.return_value = result
    monkeypatch.setattr(check_envs, 'Sandbox', Mock(return_value=sandbox))
    case = {'url': 'https://github.com/a/b/issues/1', 'library': 'a/b', 'older_ref': 'a' * 40,
            'suite_older': {'passed': 2, 'failed': 1, 'skipped': 0,
                            'failures': [{'test': 'tests/test_x.py::test_x'}]}}
    row = run_case(case, builder, object(), folder)
    builder.build.assert_called_once_with('a/b', 'a' * 40, folder)
    command = sandbox.run.call_args.args[0]
    assert command == ['/var/tmp/repro/venv/bin/python', '-m', 'pytest', '-ra', '-p', 'no:cacheprovider']
    assert row['counts_match'] == 'yes'
    assert row['baseline_recorded'] == 'NOT RECORDED'
