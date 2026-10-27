"""Deterministic comparison of a reported symptom to observed pytest output."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from repro.parser import IssueRecord, normalize_signature
from repro.tools import SymptomMatch

_EXCEPTION = re.compile(
    r'^\s*(?:E\s+)?(?P<type>(?:[A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt)'
    r'|Exception|Warning|StopIteration|GeneratorExit))'
    r'(?::[ \t]*(?P<message>[^\r\n]*))?[ \t]*$', re.MULTILINE)
_PY_FRAME = re.compile(r'^\s*File "([^"\n]+)", line \d+, in ([\w.<>]+)', re.MULTILINE)
_IPY_FRAME = re.compile(r'^\s*File\s+(.+?\.py):\d+,\s+in\s+([\w.]+)', re.MULTILINE)
_PYTEST_FRAME = re.compile(r'^\s*(.+?\.py):\d+:\s+in\s+([\w.<>]+)', re.MULTILINE)
_PYTEST_LOCATION = re.compile(r'^\s*(.+?\.py):\d+:\s+(?:[\w.]*Error|[\w.]*Exception)\s*$', re.MULTILINE)
_FUNCTION = re.compile(r'^\s*(?:>\s*)?(?:async\s+)?def\s+(\w+)\s*\(', re.MULTILINE)
_ASSERTION = re.compile(r'^\s*E\s+assert\s+(.+?)\s*==\s*(.+?)\s*$', re.MULTILINE)


@dataclass(frozen=True)
class FailureSignature:
    exception_type: str
    message: str | None
    frame: str | None


def _filename(path: str) -> str:
    return re.split(r'[/\\]', path.strip())[-1]


def extract_failure(output: str) -> FailureSignature | None:
    """Extract the final exception, excluding pytest's short summary."""
    if not isinstance(output, str):
        return None
    body = re.split(r'^=+\s*short test summary info\s*=+', output, maxsplit=1, flags=re.MULTILINE)[0]
    errors = list(_EXCEPTION.finditer(body))
    if not errors:
        return None
    error = errors[-1]
    if (not error.group(0).lstrip().startswith('E ') and
            'Traceback (most recent call last)' not in body[:error.start()] and
            not any(pattern.search(body[:error.start()]) for pattern in
                    (_PY_FRAME, _IPY_FRAME, _PYTEST_FRAME))):
        return None
    exception_type = error['type'].split('.')[-1]
    raw = error['message']
    message = normalize_signature(exception_type, raw) if raw is not None else None
    before = body[:error.start()]
    frames: list[tuple[int, str]] = []
    for pattern in (_PY_FRAME, _IPY_FRAME, _PYTEST_FRAME):
        frames.extend((match.start(), f'{_filename(match[1])}:{match[2].split(".")[-1]}')
                      for match in pattern.finditer(before))
    # pytest's innermost frame often appears as a displayed `def` followed by
    # `E ...` and then a file:line:Exception location, rather than `in name`.
    locations = list(_PYTEST_LOCATION.finditer(body[error.end():]))
    functions = list(_FUNCTION.finditer(before))
    if locations and functions:
        match = locations[0]
        function = functions[-1]
        frames.append((function.start(), f'{_filename(match[1])}:{function[1]}'))
    frames.sort(key=lambda item: item[0])
    return FailureSignature(exception_type, message, frames[-1][1] if frames else None)


def _literal(value: str) -> tuple[type, object]:
    value = value.strip()
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        parsed = value
    return type(parsed), parsed


class DeterministicSymptomChecker:
    """Conservative matcher; no model is consulted and no confidence is inferred."""

    def check(self, issue: IssueRecord, output: str) -> SymptomMatch:
        symptom = issue.symptom
        if symptom.kind == 'wrong_output':
            if issue.actual is None or issue.expected is None:
                return SymptomMatch('none', 'Reported actual and expected output are required')
            comparisons = list(_ASSERTION.finditer(output))
            for match in comparisons:
                if (_literal(match[1]) == _literal(issue.actual) and
                        _literal(match[2]) == _literal(issue.expected)):
                    return SymptomMatch('exact', 'Observed assertion matches reported actual and expected output')
            return SymptomMatch('none', 'No matching observed output comparison')
        if symptom.kind != 'exception':
            return SymptomMatch('none', 'This symptom kind has no deterministic matcher yet')
        observed = extract_failure(output)
        if observed is None or not symptom.type or observed.exception_type != symptom.type.split('.')[-1]:
            return SymptomMatch('none', 'Final observed exception type does not match')
        signature = symptom.signature or ''
        expected_message, sep, expected_frame = signature.partition(' @ ')
        if not sep:
            expected_frame = None
        if (observed.message is not None and expected_message and
                observed.message == expected_message and expected_frame and
                observed.frame == expected_frame):
            return SymptomMatch('exact', 'Exception type, normalized message and frame match')
        return SymptomMatch('partial', 'Exception type matches, but message or frame is missing or differs')
