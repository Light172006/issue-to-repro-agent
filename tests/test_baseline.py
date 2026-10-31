import json
import random
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest

from repro.baseline import baseline_from_result, baseline_rejection, load_baseline
from repro.matcher import extract_failure
from repro.parser import IssueRecord, Symptom
from repro.verifier import verify

OUTPUT = '''____________________________ test_old ____________________________
    def old():
>       raise ValueError("broken")
E       ValueError: broken
lib.py:12: ValueError
=========================== short test summary info ============================
FAILED tests/test_old.py::test_old - ValueError: broken
=================== 1 failed, 3 passed, 2 skipped in 0.1s ====================
'''


def result(output=OUTPUT, exit_code=1, timed_out=False, original_length=None):
    return SimpleNamespace(output=output, exit_code=exit_code, timed_out=timed_out,
                           original_length=original_length)


def test_failed_baseline_records_signature_and_test_id():
    baseline = baseline_from_result(result())
    assert baseline['status'] == 'complete'
    assert baseline['counts'] == {'passed': 3, 'failed': 1, 'skipped': 2}
    assert baseline['failures'][0]['test'] == 'tests/test_old.py::test_old'
    assert baseline['failures'][0]['pre_existing'] is True
    assert len(baseline['failures'][0]['signature']) == 64


def test_passing_baseline_and_distinct_failure():
    baseline = baseline_from_result(result('=== 4 passed, 1 skipped in 0.1s ===', 0))
    assert baseline['status'] == 'complete'
    assert not baseline['failures']
    assert baseline_rejection(baseline, OUTPUT) is None


@pytest.mark.parametrize(('value', 'expected'), [
    (result('=== 1 error in 0.1s ===', 2), 'collection_error'),
    (result('ERROR collecting test module', 2), 'collection_error'),
    (result('', None, True), 'timeout'),
    (result('No module named pytest', 1), 'runner_error'),
    (result(OUTPUT, 1, original_length=999999), 'truncated'),
    (result('=== 2 skipped in 0.1s ===', 0), 'no_tests'),
])
def test_inconclusive_baseline_never_means_zero_failures(value, expected):
    baseline = baseline_from_result(value)
    assert baseline['status'] == expected
    assert baseline['counts'] is None
    assert baseline_rejection(baseline, OUTPUT)


def test_corrupt_environment_is_inconclusive(tmp_path):
    (tmp_path / 'environment.json').write_text('{invalid')
    assert load_baseline(tmp_path / 'environment.json')['status'] == 'unavailable'


def test_same_signature_or_test_id_rejected_but_different_allowed():
    baseline = baseline_from_result(result())
    assert baseline_rejection(baseline, OUTPUT)
    different = OUTPUT.replace('ValueError: broken', 'ValueError: different').replace(
        'tests/test_old.py::test_old', 'tests/test_new.py::test_new')
    assert baseline_rejection(baseline, different) is None


def test_baseline_failure_property_random_ids():
    randomizer = random.Random(17)
    signature = extract_failure(OUTPUT)
    issue = IssueRecord(repo='example/lib', issue=1,
                        symptom=Symptom(kind='exception', type=signature.exception_type,
                                        signature=signature.message + ' @ ' + signature.frame))
    for _ in range(100):
        n = randomizer.randrange(100000)
        baseline = baseline_from_result(result(OUTPUT.replace('test_old', f'test_{n}')))
        assert baseline_rejection(baseline, OUTPUT)
        verified = verify(issue, b'def test_old(): pass', 'image', None, runs=None,
                          runner=lambda *args, **kwargs: result(), baseline=baseline)
        assert verified['status'] != 'reproduced'


def test_verifier_accepts_a_different_failure():
    original = extract_failure(OUTPUT)
    issue = IssueRecord(repo='example/lib', issue=1,
                        symptom=Symptom(kind='exception', type=original.exception_type,
                                        signature=original.message + ' @ ' + original.frame))
    other = OUTPUT.replace('ValueError: broken', 'ValueError: unrelated').replace('test_old', 'test_other')
    baseline = baseline_from_result(result(other))
    verified = verify(issue, b'def test_old(): pass', 'image', None, runs=None,
                      runner=lambda *args, **kwargs: result(), baseline=baseline)
    assert verified['status'] == 'reproduced'


def test_builder_records_offline_baseline(tmp_path, monkeypatch):
    from repro import envbuilder
    image = SimpleNamespace(id='image-id')
    client = Mock()
    client.images.get.return_value = image
    monkeypatch.setattr(envbuilder, 'resolve_commit', lambda *args: ('a' * 40, 'v1'))
    sandbox = MagicMock()
    sandbox.__enter__.return_value = sandbox
    sandbox.run.side_effect = [result('{"python":"3.11.0","packages":[]}', 0), result()]
    monkeypatch.setattr(envbuilder, 'Sandbox', Mock(return_value=sandbox))
    metadata = envbuilder.EnvironmentBuilder(client, Mock()).build('a/b', 'v1', tmp_path)
    saved = json.loads((tmp_path / 'environment.json').read_text())
    assert saved['baseline'] == metadata['baseline']
    assert saved['resolved_packages'] == []
    assert saved['resolution']['strategy'] == 'unbounded_latest'
    assert saved['baseline']['failures'][0]['pre_existing'] is True
    assert sandbox.run.call_count == 2


def test_parallel_atomic_metadata_writes_are_valid(tmp_path):
    from repro.envbuilder import _write_json
    path = tmp_path / 'environment.json'
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: _write_json(path, {'number': i}), range(40)))
    assert json.loads(path.read_text())['number'] in range(40)
    assert list(tmp_path.iterdir()) == [path]


def test_missing_baseline_never_verifies():
    original = extract_failure(OUTPUT)
    issue = IssueRecord(repo='example/lib', issue=1,
                        symptom=Symptom(kind='exception', type=original.exception_type,
                                        signature=original.message + ' @ ' + original.frame))
    verified = verify(issue, b'def test_old(): pass', 'image', None, runs=None,
                      runner=lambda *args, **kwargs: result())
    assert verified['status'] == 'not_reproduced'


def test_same_test_id_rejected_even_when_signature_differs():
    baseline = baseline_from_result(result())
    observed = OUTPUT.replace('ValueError: broken', 'ValueError: different')
    assert baseline_rejection(baseline, observed)
