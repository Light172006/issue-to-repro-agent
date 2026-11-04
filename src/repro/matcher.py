"""Deterministic comparison of a reported symptom to observed pytest output."""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from repro.parser import IssueRecord, normalize_signature
from repro.tools import SymptomMatch

_EXCEPTION = re.compile(
    r'^\s*(?:E\s+)?(?P<type>(?:[A-Za-z_][\w.]*(?:Error|Exception|Warning|Exit|Interrupt|Invalid)'
    r'|Exception|Warning|StopIteration|GeneratorExit|Invalid))'
    r'(?::[ \t]*(?P<message>[^\r\n]*))?[ \t]*$', re.MULTILINE)
_ANSI = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')
_PY_FRAME = re.compile(r'^\s*File "([^"\n]+)", line \d+, in ([\w.<>]+)', re.MULTILINE)
_IPY_FRAME = re.compile(r'^\s*File\s+(.+?\.py):\d+,\s+in\s+([\w.]+)', re.MULTILINE)
_PYTEST_FRAME = re.compile(r'^\s*(.+?\.py):\d+:\s+in\s+([\w.<>]+)', re.MULTILINE)
_PYTEST_LOCATION = re.compile(r'^\s*(.+?\.py):\d+:\s+(?:[\w.]*Error|[\w.]*Exception|[\w.]*Invalid)\s*$', re.MULTILINE)
_FUNCTION = re.compile(r'^\s*(?:>\s*)?(?:async\s+)?def\s+(\w+)\s*\(', re.MULTILINE)
_ASSERTION = re.compile(
    r'^\s*E\s+(?:AssertionError:\s+)?assert\s+(.+?)\s*(?:==|is|!=|is\s+not|in|not\s+in)\s+(.+?)\s*$',
    re.MULTILINE
)


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
    output = _ANSI.sub('', output)
    body = re.split(r'^=+\s*short test summary info\s*=+', output, maxsplit=1, flags=re.MULTILINE)[0]
    errors = list(_EXCEPTION.finditer(body))
    if not errors:
        locations = list(_PYTEST_LOCATION.finditer(body))
        if not locations:
            return None
        loc_match = re.match(r'^\s*(?P<path>.+?\.py):\d+:\s+(?P<type>[\w.]*(?:Error|Exception|Invalid))\s*$',
                             locations[-1].group(0))
        if not loc_match:
            return None
        exception_type = loc_match['type'].split('.')[-1]
        before = body[:locations[-1].start()]
        functions = list(_FUNCTION.finditer(before))
        frame = f'{_filename(loc_match["path"])}:{functions[-1][1]}' if functions else None
        return FailureSignature(exception_type, None, frame)
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


def _normalize_repr(s: str) -> str:
    s = s.strip().strip("'\"")
    m = re.search(r'\b(?:datetime\.)?time\s*\(\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*(\d+))?', s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        sec = int(m.group(3)) if m.group(3) else 0
        if sec:
            return f"{h:02d}:{mn:02d}:{sec:02d}"
        return f"{h:02d}:{mn:02d}"
    m2 = re.match(r'^(\d{1,2}):(\d{2}):00$', s)
    if m2:
        return f"{int(m2.group(1)):02d}:{m2.group(2)}"
    m3 = re.match(r'^(\d{1,2}):(\d{2})$', s)
    if m3:
        return f"{int(m3.group(1)):02d}:{m3.group(2)}"
    return s


def _value_matches(obs: str, target: str) -> bool:
    obs = obs.strip()
    target = target.strip()
    if not obs or not target:
        return False
    # 1. Exact literal equivalence (e.g. [1] == [1], 0 == 0, 'foo' == 'foo')
    try:
        p_obs = ast.literal_eval(obs)
        p_tgt = ast.literal_eval(target)
        if type(p_obs) is type(p_tgt) and p_obs == p_tgt:
            return True
    except (ValueError, SyntaxError):
        pass

    # 2. String equality
    if obs.casefold() == target.casefold():
        return True

    # 3. Canonical representation equality (e.g. datetime.time(15, 0) vs "15:00" vs "15:00:00")
    norm_obs = _normalize_repr(obs)
    norm_target = _normalize_repr(target)
    if norm_obs.casefold() == norm_target.casefold():
        return True

    # 4. Target is an explanatory sentence containing the observed literal or repr
    # e.g., target="None - empty string should not parse as a time", obs="None"
    # or target="parse(...) returns <Result (...)>", obs="<Result (...)>"
    for val in (obs, norm_obs):
        if re.search(r'(?:\b|[\'\"`])' + re.escape(val) + r'(?:\b|[\'\"`])', target):
            return True
        if len(val) >= 3 and val in target:
            return True

    # 5. Empty collection matching semantic description "empty"
    try:
        p_obs = ast.literal_eval(obs)
        if (isinstance(p_obs, (list, tuple, set, dict, str, bytes)) and len(p_obs) == 0 and
                re.search(r'\bempty\b', target, re.IGNORECASE)):
            return True
    except (ValueError, SyntaxError):
        pass

    return False


class DeterministicSymptomChecker:
    """Conservative matcher; no model is consulted and no confidence is inferred."""

    def __init__(self, baseline: dict | None = None):
        self.baseline = baseline

    def check(self, issue: IssueRecord, output: str) -> SymptomMatch:
        if self.baseline is not None:
            from repro.baseline import baseline_rejection
            reason = baseline_rejection(self.baseline, output)
            if reason:
                return SymptomMatch('none', reason)
        symptom = issue.symptom
        if symptom.kind == 'wrong_output':
            if issue.actual is None or issue.expected is None:
                return SymptomMatch('none', 'Reported actual and expected output are required')
            comparisons = list(_ASSERTION.finditer(output))
            for match in comparisons:
                left, right = match[1], match[2]
                if ((_value_matches(left, issue.actual) and _value_matches(right, issue.expected)) or
                        (_value_matches(left, issue.expected) and _value_matches(right, issue.actual))):
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
