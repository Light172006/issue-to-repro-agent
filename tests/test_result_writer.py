import json

import pytest

from repro.agent import AgentResult
from repro.result_writer import ArtifactError, write_run_artifacts


def candidate(path='/work/repro/test_example.py', verdict='exact'):
    return AgentResult('candidate_found', path, verdict, 3, '0.012', 1.5)


@pytest.mark.parametrize('verdict', ['exact', 'partial'])
def test_saves_confirmed_candidate_without_claiming_verification(tmp_path, verdict):
    repro = tmp_path / 'repro'
    repro.mkdir()
    source = b'def test_example():\n    assert 1 == 2\n'
    (repro / 'test_example.py').write_bytes(source)
    result = write_run_artifacts(tmp_path, candidate(verdict=verdict))
    assert (tmp_path / 'test_repro.py').read_bytes() == source
    assert result == json.loads((tmp_path / 'result.json').read_text())
    assert result['outcome'] == 'candidate_found'
    assert result['status'] == 'not_reproduced'
    assert result['verification'] == 'pending'
    assert result['confidence'] is None
    assert result['checks'] == {'symptom_match': verdict, 'repeated_runs': None, 'fixed_version': None}
    assert result['cost_usd'] == '0.012'
    assert result['test_file'] == 'test_repro.py'


def test_unsuccessful_run_does_not_save_test(tmp_path):
    result = AgentResult('gave_up', None, None, 1, '0', 1.0, reason='gave up')
    data = write_run_artifacts(tmp_path, result)
    assert data['verification'] == 'not_run'
    assert data['status'] == 'not_reproduced'
    assert not (tmp_path / 'test_repro.py').exists()
    assert (tmp_path / 'result.json').exists()


@pytest.mark.parametrize('path', ['/etc/passwd', '/work/repro/../outside.py',
                                  '/work/reproduction/test.py', '/work/repro/bad.txt'])
def test_rejects_invalid_candidate_paths(tmp_path, path):
    with pytest.raises(ArtifactError):
        write_run_artifacts(tmp_path, candidate(path=path))
    assert not (tmp_path / 'test_repro.py').exists()


def test_rejects_unconfirmed_and_invalid_tests(tmp_path):
    repro = tmp_path / 'repro'
    repro.mkdir()
    (repro / 'test_example.py').write_text('def broken(:\n', encoding='utf-8')
    with pytest.raises(ArtifactError):
        write_run_artifacts(tmp_path, candidate())
    (repro / 'test_example.py').write_text('print("no tests")\n', encoding='utf-8')
    with pytest.raises(ArtifactError):
        write_run_artifacts(tmp_path, candidate())
    with pytest.raises(ArtifactError):
        write_run_artifacts(tmp_path, candidate(verdict='none'))
    assert not (tmp_path / 'test_repro.py').exists()


def test_rejects_symlink_candidate(tmp_path):
    repro = tmp_path / 'repro'
    repro.mkdir()
    outside = tmp_path / 'outside.py'
    outside.write_text('def test_example(): pass\n', encoding='utf-8')
    try:
        (repro / 'test_example.py').symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip('File symlinks are not supported for this user')
    with pytest.raises(ArtifactError):
        write_run_artifacts(tmp_path, candidate())
    assert not (tmp_path / 'test_repro.py').exists()


def test_oversized_candidate_is_rejected(tmp_path):
    repro = tmp_path / 'repro'
    repro.mkdir()
    (repro / 'test_example.py').write_bytes(b'#' * 65537)
    with pytest.raises(ArtifactError, match='too large'):
        write_run_artifacts(tmp_path, candidate())
    assert not (tmp_path / 'test_repro.py').exists()


def test_saved_previous_candidate_can_be_finalized_without_model(tmp_path):
    import subprocess
    import sys
    from dataclasses import asdict
    from pathlib import Path

    from repro.parser import IssueRecord, Symptom

    root = Path(__file__).resolve().parents[1]
    repro = tmp_path / 'repro'
    repro.mkdir()
    (repro / 'test_example.py').write_text('def test_example():\n    assert False\n', encoding='utf-8')
    (tmp_path / 'result.json').write_text(json.dumps(asdict(candidate())), encoding='utf-8')
    issue = IssueRecord(repo='fictional/project', issue=1,
                        symptom=Symptom(kind='exception', type='ValueError',
                                        signature='ValueError: bad @ example.py:run'))
    (tmp_path / 'parser_trace.jsonl').write_text(json.dumps({'event': 'parser_result',
        'fallback': False, 'record': issue.model_dump()}) + '\n', encoding='utf-8')
    (tmp_path / 'trace.jsonl').write_text(json.dumps({'tool': 'submit_repro',
        'arguments': {'path': '/work/repro/test_example.py'},
        'output': 'File "example.py", line 1, in run\nValueError: bad\n'}) + '\n', encoding='utf-8')
    command = [sys.executable, str(root / 'scripts' / 'save_step8_candidate.py'), str(tmp_path)]
    for _ in range(2):
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
    assert (tmp_path / 'test_repro.py').read_text() == 'def test_example():\n    assert False\n'
    assert json.loads((tmp_path / 'result.json').read_text())['verification'] == 'pending'


def test_saved_test_fails_when_executed_outside_agent(tmp_path):
    import subprocess
    import sys

    repro = tmp_path / 'repro'
    repro.mkdir()
    (repro / 'test_example.py').write_text('def test_example():\n    assert 1 == 2\n', encoding='utf-8')
    write_run_artifacts(tmp_path, candidate())
    result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                             str(tmp_path / 'test_repro.py')], capture_output=True, text=True,
                            check=False)
    assert result.returncode == 1
    assert '1 failed' in result.stdout
    assert 'assert 1 == 2' in result.stdout


def test_existing_candidate_requires_saved_match_evidence(tmp_path):
    import subprocess
    import sys
    from dataclasses import asdict
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    repro = tmp_path / 'repro'
    repro.mkdir()
    (repro / 'test_example.py').write_text('def test_example():\n    assert False\n', encoding='utf-8')
    (tmp_path / 'result.json').write_text(json.dumps(asdict(candidate())), encoding='utf-8')
    result = subprocess.run([sys.executable, str(root / 'scripts' / 'save_step8_candidate.py'), str(tmp_path)],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 1
    assert not (tmp_path / 'test_repro.py').exists()


def test_nonreproduction_reason_is_preserved(tmp_path):
    data = write_run_artifacts(tmp_path, AgentResult('gave_up', None, None, 1, '0', 1, reason='Timeout'))
    assert data['status'] == 'not_reproduced'
    assert data['status_detail'] == 'Timeout'
