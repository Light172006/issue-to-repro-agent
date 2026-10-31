import subprocess
from pathlib import Path

import pytest

from repro.installenv import resolve_install


def scripted_run(responses):
    calls = []
    def run(command, timeout):
        calls.append((command, timeout))
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    return run, calls


def test_date_bounded_install_records_commit_cutoff(tmp_path):
    run, calls = scripted_run([(0, '2020-01-02T01:02:03+00:00\n'), (0, ''), (0, ''), (0, ''), (0, '')])
    result = resolve_install(Path('/repo'), tmp_path, ['pytest<8'], run=run, clock=lambda: 10)
    assert result == {'strategy': 'date_bounded', 'reason_for_fallback': None,
                      'cutoff': '2020-01-02T01:02:03+00:00', 'install_duration_s': 0}
    assert calls[-1][0][-3:] == ['/repo', 'pytest', 'pytest<8']
    assert '--exclude-newer' in calls[-1][0]


def test_old_date_with_no_matching_release_falls_back(tmp_path):
    run, calls = scripted_run([(0, '2001-01-01T00:00:00Z'), (0, ''), (0, ''), (0, ''),
                               (1, 'No solution found when resolving dependencies'), (0, ''), (0, '')])
    result = resolve_install(Path('/repo'), tmp_path, [], run=run, clock=lambda: 5)
    assert result['strategy'] == 'unbounded_latest'
    assert result['reason_for_fallback'] == 'date_bounded_resolution_failed'
    assert '--exclude-newer' not in calls[-1][0]


def test_double_resolution_failure_is_classified(tmp_path):
    run, _ = scripted_run([(0, '2020-01-01T00:00:00Z'), (0, ''), (0, ''), (0, ''),
                           (1, 'No solution found'), (0, ''), (1, 'No solution found')])
    with pytest.raises(RuntimeError, match='dependency resolution failed'):
        resolve_install(Path('/repo'), tmp_path, [], run=run)


def test_network_and_build_errors_do_not_silently_fallback(tmp_path):
    run, calls = scripted_run([(0, '2020-01-01T00:00:00Z'), (0, ''), (0, ''), (0, ''),
                               (1, 'connection refused')])
    with pytest.raises(RuntimeError, match='environment installation failed'):
        resolve_install(Path('/repo'), tmp_path, [], run=run)
    assert len(calls) == 5


def test_hung_install_is_classified(tmp_path):
    run, _ = scripted_run([(0, '2020-01-01T00:00:00Z'), (0, ''), (0, ''), (0, ''),
                           subprocess.TimeoutExpired('uv', 1)])
    with pytest.raises(TimeoutError, match='install timeout'):
        resolve_install(Path('/repo'), tmp_path, [], run=run)


@pytest.mark.parametrize('date', ['', 'invalid', '2020-01-01T00:00:00'])
def test_bad_commit_date_fails_closed(tmp_path, date):
    run, _ = scripted_run([(0, date)])
    with pytest.raises(RuntimeError, match='commit timestamp'):
        resolve_install(Path('/repo'), tmp_path, [], run=run)


def test_resolution_selection_is_deterministic(tmp_path):
    def once():
        run, _ = scripted_run([(0, '2020-01-01T00:00:00Z'), (0, ''), (0, ''), (0, ''), (0, '')])
        return resolve_install(Path('/repo'), tmp_path, [], run=run, clock=lambda: 1)
    assert once() == once()
