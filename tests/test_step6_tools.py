from repro.parser import IssueRecord, Symptom
from repro.tools import NaiveSymptomChecker


def issue(kind='exception', typ='KeyError', signature='KeyError: <n> @ file.py:lookup'):
    return IssueRecord(repo='example/library', issue=1,
                       symptom=Symptom(kind=kind, type=typ, signature=signature))


def test_checker_exact_requires_both_exception_and_function():
    check = NaiveSymptomChecker()
    assert check.check(issue(), 'File "file.py", line 3, in lookup\nKeyError: 42').verdict == 'exact'
    assert check.check(issue(), 'KeyError: 42').verdict == 'partial'
    assert check.check(issue(), 'OtherKeyError: 42 in lookup').verdict == 'none'


def test_checker_rejects_non_exception_symptoms():
    result = NaiveSymptomChecker().check(issue(kind='wrong_output', typ=None), 'wrong output')
    assert result.verdict == 'none' and 'Step 7' in result.reason


def test_checker_escapes_exception_and_requires_frame():
    check = NaiveSymptomChecker()
    assert check.check(issue(signature=None), 'KeyError').verdict == 'partial'
    assert check.check(issue(typ='A.BError'), 'AxBError').verdict == 'none'
