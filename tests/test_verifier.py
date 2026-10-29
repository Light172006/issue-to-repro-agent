import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from repro.parser import IssueRecord, Symptom
from repro.verifier import save_verification, verify

CASES = json.loads((Path(__file__).parent / 'fixtures' / 'matcher_cases.json').read_text())
CASE = next(case for case in CASES if case['kind'] == 'exception' and case['verdict'] == 'exact')
ISSUE = IssueRecord(repo='fictional/library', issue=1,
                    symptom=Symptom(kind=CASE['kind'], type=CASE['type'], signature=CASE['signature']))


def answer(output=CASE['output'], code=1, timed_out=False):
    return SimpleNamespace(output=output, exit_code=code, timed_out=timed_out)


def run(sequence, fixed=False, issue=ISSUE):
    calls = []
    def runner(client, image, candidate, **kwargs):
        calls.append((image, candidate))
        value = sequence.pop(0)
        if isinstance(value, Exception):
            raise value
        return value
    data = verify(issue, b'def test_x(): pass', 'buggy', None, runs=Path('runs'),
                  fixed_image='fixed' if fixed else None, fixed_ref='2.0' if fixed else None,
                  runner=runner)
    return data, calls


def test_high_requires_five_exact_failures_and_fixed_pass():
    data, calls = run([answer() for _ in range(5)] + [answer('1 passed in 0.1s', 0)], True)
    assert (data['status'], data['confidence']) == ('reproduced', 'high')
    assert data['checks']['repeated_runs']['consistent'] is True
    assert len(calls) == 6
    assert all(candidate == calls[0][1] for _, candidate in calls)


def test_medium_when_no_fixed_version():
    data, _ = run([answer() for _ in range(5)])
    assert (data['status'], data['confidence']) == ('reproduced', 'medium')


@pytest.mark.parametrize('fixed', [answer('1 skipped', 0), answer('1 failed', 1), answer('', None, True)])
def test_fixed_inconclusive_never_high_or_reproduced(fixed):
    data, _ = run([answer() for _ in range(5)] + [fixed], True)
    assert (data['status'], data['confidence']) == ('not_reproduced', 'low')


def test_inconsistent_runs_are_low():
    data, _ = run([answer(), answer(), answer('1 passed', 0), answer(), answer()])
    assert (data['status'], data['confidence']) == ('not_reproduced', 'low')


def test_errors_do_not_verify():
    data, _ = run([RuntimeError()] * 5)
    assert (data['status'], data['confidence']) == ('not_reproduced', None)


def test_partial_is_low_even_when_consistent():
    issue = ISSUE.model_copy(deep=True)
    issue.symptom.signature = issue.symptom.signature.replace(' @ ', ' changed @ ')
    data, _ = run([answer() for _ in range(5)], issue=issue)
    assert (data['status'], data['confidence']) == ('reproduced', 'low')


def test_write_preserves_cost_and_records_checks(tmp_path):
    (tmp_path / 'result.json').write_text('{"cost_usd": "0.03"}')
    data, _ = run([answer() for _ in range(5)])
    save_verification(tmp_path, data)
    saved = json.loads((tmp_path / 'result.json').read_text())
    assert saved['cost_usd'] == '0.03'
    assert saved['status'] == 'reproduced'


def test_time_limit_never_runs_a_container(tmp_path):
    data = verify(ISSUE, b'def test_x(): pass', 'buggy', None, runs=tmp_path,
                  deadline=0, runner=lambda *args, **kwargs: pytest.fail('must not run'))
    assert data['status'] == 'not_reproduced'
    assert data['checks']['repeated_runs']['runs'][0]['error'] == 'time limit reached'


def test_matching_different_failures_are_not_consistent():
    altered = CASE['output'].replace('Error:', 'Error: changed ', 1)
    data, _ = run([answer(), answer(), answer(altered), answer(), answer()])
    assert data['checks']['repeated_runs']['consistent'] is False
    assert data['confidence'] == 'low'
