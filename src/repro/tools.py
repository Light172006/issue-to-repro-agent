"""Step 6 symptom-checking interface; execution tools are not implemented yet."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from repro.parser import IssueRecord

Verdict = Literal['exact', 'partial', 'none']


@dataclass(frozen=True)
class SymptomMatch:
    verdict: Verdict
    reason: str


class SymptomChecker(Protocol):
    def check(self, issue: IssueRecord, output: str) -> SymptomMatch: ...


class NaiveSymptomChecker:
    """Temporary Step 6 stub, not verification; Step 7 must replace it."""

    def check(self, issue: IssueRecord, output: str) -> SymptomMatch:
        symptom = issue.symptom
        if symptom.kind != 'exception':
            return SymptomMatch('none', 'Non-exception symptoms are not supported until Step 7')
        exception = symptom.type
        if not exception or not re.search(rf'(?<![\w.]){re.escape(exception)}(?!\w)', output):
            return SymptomMatch('none', 'Expected exception type was not found')
        frame = re.search(r' @ [^\s:]+:([^\s:]+)$', symptom.signature or '')
        if frame and re.search(rf'\bin\s+{re.escape(frame.group(1))}\b', output):
            return SymptomMatch('exact', 'Exception type and frame function both appear')
        return SymptomMatch('partial', 'Exception type appears; frame function was not matched')
