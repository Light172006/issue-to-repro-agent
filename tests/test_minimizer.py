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
