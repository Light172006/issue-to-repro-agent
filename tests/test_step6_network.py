"""Explicitly opt-in paid end-to-end check; never run in ordinary tests."""
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.network
@pytest.mark.docker
@pytest.mark.skipif(os.environ.get('REPRO_PAID_E2E') != '1',
                    reason='Set REPRO_PAID_E2E=1 only after approving paid model calls')
def test_step6_paid_end_to_end():
    project = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, 'scripts/e2e_step6.py'], cwd=project,
                            capture_output=True, text=True, timeout=960, check=False)
    print(result.stdout)
    assert result.returncode == 0, result.stderr
    assert 'Outcome: candidate_found' in result.stdout
    assert 'Verdict: exact' in result.stdout or 'Verdict: partial' in result.stdout
