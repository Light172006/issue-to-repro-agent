import json
from pathlib import Path

import pytest

from repro.matcher import DeterministicSymptomChecker
from repro.parser import IssueRecord, Symptom

_CASES = json.loads((Path(__file__).parent / 'fixtures' / 'matcher_cases.json').read_text(encoding='utf-8'))


@pytest.mark.parametrize('case', _CASES, ids=lambda case: case['name'])
def test_saved_failure_output(case):
    issue = IssueRecord(repo='fictional/library', issue=1, expected=case['expected'],
                        actual=case['actual'], symptom=Symptom(kind=case['kind'],
                        type=case['type'], signature=case['signature']))
    assert DeterministicSymptomChecker().check(issue, case['output']).verdict == case['verdict']
