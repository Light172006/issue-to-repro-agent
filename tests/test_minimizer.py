from types import SimpleNamespace

from repro.matcher import DeterministicSymptomChecker
from repro.minimizer import minimize
from repro.parser import IssueRecord, Symptom

ISSUE = IssueRecord(repo='example/test', issue=1, symptom=Symptom(kind='exception', type='ValueError', signature='ValueError: bad @ library.py:broken'))
OUTPUT = '''    def broken():
>       raise ValueError("bad")
E       ValueError: bad
library.py:12: ValueError
=========================== short test summary info ============================
FAILED test_repro.py::test_x - ValueError: bad
'''


def test_reduction_preserves_required_statements_and_caches(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('import os\n\ndef helper():\n    return 3\n\ndef test_x():\n    unused = 1\n    value = helper()\n    assert value\n')
    calls = []
    def runner(data, timeout):
        text = data.decode()
        assert data not in calls
        calls.append(data)
        valid = 'def helper' in text and 'value = helper()' in text and 'assert value' in text
        return SimpleNamespace(exit_code=1 if valid else 0, output=OUTPUT if valid else '1 passed', timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {'max_runs': 100})
    assert result.status == 'minimized'
    assert result.final_lines < result.original_lines
    assert b'def helper' in result.source and b'value = helper()' in result.source
    assert b'unused' not in result.source
    assert len(calls) == result.runs


def test_invalid_and_empty_candidates_are_skipped_without_runner(tmp_path):
    path = tmp_path / 'test.py'
    path.write_bytes(b'def (')
    result = minimize(path, ISSUE, lambda *a: (_ for _ in ()).throw(AssertionError()), DeterministicSymptomChecker(), {})
    assert result.status == 'skipped' and result.runs == 0


def test_different_exception_cannot_replace_original(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('def test_x():\n    necessary = 1\n    raise ValueError("bad")\n')
    def runner(data, timeout):
        output = OUTPUT if b'necessary' in data else OUTPUT.replace('ValueError', 'NameError')
        return SimpleNamespace(exit_code=1, output=output, timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert b'necessary = 1' in result.source


def test_final_verification_failure_keeps_original(tmp_path, monkeypatch):
    import hashlib
    import json

    from repro import verifier
    from repro.minimizer import minimize_run
    original = b'def test_x():\n    unused = 1\n    raise ValueError("bad")\n'
    (tmp_path / 'test_repro.py').write_bytes(original)
    (tmp_path / 'result.json').write_text(json.dumps({'status': 'reproduced', 'verification': 'completed',
        'confidence': 'high', 'candidate_sha256': hashlib.sha256(original).hexdigest(),
        'checks': {'repeated_runs': {'runs': [{'failure': ['ValueError', 'ValueError: bad', 'library.py:broken']}]},
                   'fixed_version': {'passed': True}}}))
    monkeypatch.setattr(verifier, '_run_once', lambda *a, **kw: SimpleNamespace(exit_code=1, output=OUTPUT, timed_out=False))
    monkeypatch.setattr(verifier, 'verify', lambda *a, **kw: {'status': 'not_reproduced', 'confidence': None,
        'checks': {'repeated_runs': {'runs': []}}})
    result = minimize_run(tmp_path, ISSUE, None, 'fake', fixed_image='fixed')
    assert result['minimization']['status'] == 'failed_verification'
    assert (tmp_path / 'test_repro.py').read_bytes() == original
    assert (tmp_path / 'test_repro.orig.py').read_bytes() == original


def test_bloated_fixture_shrinks_and_keeps_dependencies(tmp_path):
    from pathlib import Path
    path = tmp_path / 'test_repro.py'
    path.write_bytes((Path(__file__).parent / 'fixtures/minimizer/bloated.py').read_bytes())
    def runner(data, timeout):
        text = data.decode()
        interesting = 'def required_helper' in text and 'value = required_helper()' in text and 'raise ValueError' in text
        return SimpleNamespace(exit_code=1 if interesting else 0, output=OUTPUT if interesting else '1 passed', timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {'max_runs': 100})
    assert result.final_lines < 15
    assert result.status == 'minimized'
    assert b'def required_helper' in result.source


def test_run_budget_returns_smallest_seen(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('import os\ndef test_x():\n    raise ValueError("bad")\n')
    runner = lambda data, timeout: SimpleNamespace(exit_code=1, output=OUTPUT, timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {'max_runs': 1})
    assert result.status == 'timeout'
    assert result.runs == 1


def test_one_minimal_for_generated_independent_statements(tmp_path):
    import random

    from repro.minimizer import remove_units, units
    rng = random.Random(47)
    for example in range(12):
        count = rng.randint(2, 9)
        required = rng.randrange(count)
        source = 'def test_x():\n' + ''.join(f'    item_{i} = {i}\n' for i in range(count)) + '    raise ValueError("bad")\n'
        path = tmp_path / f'example_{example}.py'
        path.write_text(source)
        marker = f'item_{required} = {required}'
        def runner(data, timeout, marker=marker):
            text = data.decode()
            valid = marker in text and 'raise ValueError' in text
            return SimpleNamespace(exit_code=1 if valid else 0, output=OUTPUT if valid else '1 passed', timed_out=False)
        result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {'max_runs': 100})
        final = result.source.decode()
        assert result.status != 'timeout'
        for unit in units(final, top_level=False):
            candidate = remove_units(final, [unit])
            try:
                compile(candidate, '<test>', 'exec')
            except SyntaxError:
                continue
            assert marker not in candidate or 'raise ValueError' not in candidate


def test_timeout_derived_from_measured_baseline(tmp_path, monkeypatch):
    from repro import minimizer
    ticks = iter([0, 0, 0, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12, 12])
    monkeypatch.setattr(minimizer.time, 'monotonic', lambda: next(ticks, 12))
    path = tmp_path / 'test.py'
    path.write_text('import os\ndef test_x():\n    raise ValueError("bad")\n')
    timeouts = []
    def runner(data, timeout):
        timeouts.append(timeout)
        return SimpleNamespace(exit_code=1, output=OUTPUT, timed_out=False)
    minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {'max_runs': 2, 'time_limit_s': 300})
    assert timeouts == [60, 24]


def test_whitespace_and_non_utf8_skip_without_runner(tmp_path):
    for raw in (b'', b'   \n', b'\xff\xfe'):
        path = tmp_path / 'test.py'
        path.write_bytes(raw)
        result = minimize(path, ISSUE, lambda *args: (_ for _ in ()).throw(AssertionError()),
                          DeterministicSymptomChecker(), {})
        assert result.status == 'skipped'
        assert result.runs == 0


def test_hung_and_collection_error_candidates_are_rejected(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('def test_x():\n    essential = 1\n    raise ValueError("bad")\n')
    def runner(data, timeout):
        if b'essential' in data:
            return SimpleNamespace(exit_code=1, output=OUTPUT, timed_out=False)
        return SimpleNamespace(exit_code=None, output='', timed_out=True)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert b'essential = 1' in result.source


def test_collection_errors_do_not_count_as_matching_failures(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('def test_x():\n    raise ValueError("bad")\n')
    def runner(data, timeout):
        return SimpleNamespace(exit_code=2, output='ERROR collecting test_repro.py\n' + OUTPUT, timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert result.status == 'skipped'


def test_crlf_and_comments_are_preserved_for_kept_lines(tmp_path):
    path = tmp_path / 'test.py'
    path.write_bytes(b'# important\r\ndef test_x():\r\n    raise ValueError("bad")  # keep\r\n')
    def runner(data, timeout):
        interesting = b'# keep' in data and b'raise ValueError("bad")' in data and b'def test_x' in data
        return SimpleNamespace(exit_code=1 if interesting else 0, output=OUTPUT if interesting else '', timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert b'raise ValueError("bad")  # keep\r\n' in result.source
    assert b'\r\n' in result.source


def test_model_layer_is_never_called(tmp_path, monkeypatch):
    from repro import llm
    monkeypatch.setattr(llm, 'call_model', lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError('model called')))
    path = tmp_path / 'test.py'
    path.write_text('def test_x():\n    raise ValueError("bad")\n')
    def runner(data, timeout):
        valid = b'raise ValueError' in data and b'def test_x' in data
        return SimpleNamespace(exit_code=1 if valid else 0, output=OUTPUT if valid else '', timed_out=False)
    assert minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {}).runs > 0


def test_input_literals_are_shortened_only_when_failure_stays_same(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('def test_x():\n    value = "abcdefgh"\n    raise ValueError("bad")\n')
    def runner(data, timeout):
        text = data.decode()
        valid = 'value = ' in text and 'raise ValueError' in text and 'def test_x' in text
        return SimpleNamespace(exit_code=1 if valid else 0, output=OUTPUT if valid else '', timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert b"value = ''" in result.source
    assert result.status == 'minimized'


def test_lower_confidence_reverts_original(tmp_path, monkeypatch):
    import hashlib
    import json

    from repro import verifier
    from repro.minimizer import minimize_run
    original = b'def test_x():\n    unused = 1\n    raise ValueError("bad")\n'
    (tmp_path / 'test_repro.py').write_bytes(original)
    before = {'status': 'reproduced', 'verification': 'completed', 'confidence': 'high',
              'candidate_sha256': hashlib.sha256(original).hexdigest(),
              'checks': {'repeated_runs': {'runs': [{'failure': ['ValueError', 'ValueError: bad', 'library.py:broken']}]},
                         'fixed_version': {'passed': True, 'commit': 'a' * 40}}}
    (tmp_path / 'result.json').write_text(json.dumps(before))
    monkeypatch.setattr(verifier, '_run_once', lambda *a, **kw: SimpleNamespace(exit_code=1, output=OUTPUT, timed_out=False))
    monkeypatch.setattr(verifier, 'verify', lambda *a, **kw: {'status': 'reproduced', 'confidence': 'low',
        'checks': {'repeated_runs': {'runs': [{'failure': ['ValueError', 'ValueError: bad', 'library.py:broken']}]},
                   'fixed_version': {'passed': True}}})
    result = minimize_run(tmp_path, ISSUE, None, 'fake', fixed_image='fixed')
    assert result['minimization']['status'] == 'failed_verification'
    assert result['confidence'] == 'high'
    assert (tmp_path / 'test_repro.py').read_bytes() == original


def test_deterministic_output_and_decorated_fixture_dependencies(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('''import pytest

@pytest.fixture
def dependency():
    return 42

@pytest.mark.parametrize("value", [1, 2])
def test_x(dependency, value):
    ignored = 0
    assert dependency == 42
    raise ValueError("bad")
''')
    def runner(data, timeout):
        text = data.decode()
        valid = all(fragment in text for fragment in ('import pytest', '@pytest.fixture',
                    'def dependency', '@pytest.mark.parametrize', 'def test_x', 'raise ValueError'))
        return SimpleNamespace(exit_code=1 if valid else 0, output=OUTPUT if valid else '', timed_out=False)
    first = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    second = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert first.source == second.source
    assert b'ignored' not in first.source
    assert b'@pytest.fixture' in first.source


def test_invalid_intermediate_candidates_never_reach_runner(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('def test_x():\n    if True:\n        raise ValueError("bad")\n')
    calls = []
    def runner(data, timeout):
        compile(data, 'test.py', 'exec')
        calls.append(data)
        valid = b'raise ValueError' in data
        return SimpleNamespace(exit_code=1 if valid else 0, output=OUTPUT if valid else '', timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert result.runs == len(calls)


def test_import_error_is_not_the_original_failure(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('import important\ndef test_x():\n    raise ValueError("bad")\n')
    def runner(data, timeout):
        output = OUTPUT if b'import important' in data else OUTPUT.replace('ValueError', 'ImportError')
        return SimpleNamespace(exit_code=1, output=output, timed_out=False)
    assert b'import important' in minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {}).source


def test_unverified_run_is_skipped_without_candidate_or_model(tmp_path):
    import json

    from repro.minimizer import minimize_run
    (tmp_path / 'result.json').write_text(json.dumps({'status': 'not_reproduced', 'verification': 'pending'}))
    result = minimize_run(tmp_path, ISSUE, None, 'unused')
    assert result['minimization']['status'] == 'skipped'


def test_minimal_one_line_test_is_unchanged(tmp_path):
    path = tmp_path / 'test.py'
    path.write_text('def test_x(): raise ValueError("bad")\n')
    def runner(data, timeout):
        valid = b'def test_x(): raise ValueError("bad")' in data
        return SimpleNamespace(exit_code=1 if valid else 0, output=OUTPUT if valid else '', timed_out=False)
    result = minimize(path, ISSUE, runner, DeterministicSymptomChecker(), {})
    assert result.status == 'unchanged'
    assert result.source == path.read_bytes()
