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


def test_matcher_wrong_output_is_operator_and_reverse_order():
    issue = IssueRecord(
        repo='r1chardj0n3s/parse',
        issue=272,
        expected='None - empty string should not parse as a time',
        actual='parse("{:tt}", "") returns <Result (datetime.time(0, 0),) {}>',
        symptom=Symptom(kind='wrong_output', type=None, signature=None)
    )
    # Forward check: assert actual is expected
    out1 = "E       assert <Result (datetime.time(0, 0),) {}> is None\n"
    assert DeterministicSymptomChecker().check(issue, out1).verdict == 'exact'

    # Reverse check in test: assert None is actual
    out2 = "E       assert None is <Result (datetime.time(0, 0),) {}>\n"
    assert DeterministicSymptomChecker().check(issue, out2).verdict == 'exact'

    # Mismatched value
    out3 = "E       assert 'other' is None\n"
    assert DeterministicSymptomChecker().check(issue, out3).verdict == 'none'


def test_matcher_canonical_time_representations():
    issue = IssueRecord(
        repo='r1chardj0n3s/parse',
        issue=258,
        expected='15:00',
        actual='datetime.time(3, 0)',
        symptom=Symptom(kind='wrong_output', type=None, signature=None)
    )
    # Pytest output: assert datetime.time(3, 0) == datetime.time(15, 0)
    out = "E       assert datetime.time(3, 0) == datetime.time(15, 0)\n"
    assert DeterministicSymptomChecker().check(issue, out).verdict == 'exact'

    # String representation in test: assert '03:00:00' == '15:00:00'
    out_str = "E       AssertionError: assert '03:00:00' == '15:00:00'\n"
    assert DeterministicSymptomChecker().check(issue, out_str).verdict == 'exact'


def test_matcher_empty_collection_semantics():
    issue = IssueRecord(
        repo='more-itertools/more-itertools',
        issue=1309,
        expected='bucket should be empty',
        actual='[1], expected []',
        symptom=Symptom(kind='wrong_output', type=None, signature=None)
    )
    out = "E       assert [1] == []\n"
    assert DeterministicSymptomChecker().check(issue, out).verdict == 'exact'
