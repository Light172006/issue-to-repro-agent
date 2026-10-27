import os
import subprocess
import sys

import pytest


@pytest.mark.network
def test_gold_set_real_calls():
    if os.getenv('REPRO_PARSER_GOLD_RUN') != '1':
        pytest.skip('Set REPRO_PARSER_GOLD_RUN=1 after labelling all 10 issues and reviewing cost')
    result = subprocess.run([sys.executable, 'bench/score_parser.py', '--run'], check=False)
    assert result.returncode == 0
