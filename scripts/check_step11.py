"""Exercise Step 11's two early exits locally without model calls or Docker."""
from __future__ import annotations

from repro.parser import IssueRecord
from repro.triage import assess


def main() -> int:
    cases = [
        ('hardware', {'body': 'The reproduction requires a GPU.', 'comments': []},
         IssueRecord(repo='example/project', issue=1), 'not_feasible'),
        ('vague', {'body': 'Something broke.', 'comments': []},
         IssueRecord(repo='example/project', issue=2,
                     missing=['steps', 'actual behavior', 'minimal code']), 'needs_info'),
    ]
    passed = True
    for name, issue, record, expected in cases:
        result = assess(issue, record)
        ok = result is not None and result.status == expected
        passed &= ok
        print(f'{name}: {"PASS" if ok else "FAIL"}; status={result.status if result else "none"}')
        if result:
            print(f'  reason: {result.reason}')
            for question in result.questions:
                print(f'  question: {question}')
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
