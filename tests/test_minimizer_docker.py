import os
from contextlib import closing
from pathlib import Path

import pytest

from repro.matcher import DeterministicSymptomChecker
from repro.minimizer import minimize
from repro.parser import IssueRecord, Symptom
from repro.verifier import _run_once


@pytest.mark.docker
def test_minimizer_with_boltons_image(tmp_path):
    if not os.getenv('REPRO_DOCKER_TESTS') or not os.getenv('REPRO_STEP10_IMAGE'):
        pytest.skip('Set REPRO_DOCKER_TESTS=1 and REPRO_STEP10_IMAGE to the buggy boltons image')
    import docker
    record = IssueRecord(repo='mahmoud/boltons', issue=337, symptom=Symptom(
        kind='exception', type='AttributeError',
        signature="AttributeError: 'OrderedMultiDict' object has no attribute 'root' @ dictutils.py:_insert"))
    candidate = Path('tests/fixtures/minimizer/boltons_bloated.py')
    with closing(docker.from_env()) as client:
        def runner(data, timeout):
            return _run_once(client, os.environ['REPRO_STEP10_IMAGE'], data, runs=tmp_path / 'runs', timeout=timeout)
        result = minimize(candidate, record, runner, DeterministicSymptomChecker(), {'max_runs': 100})
    assert result.status == 'minimized'
    assert result.final_lines < 15
    assert result.final_lines < result.original_lines
