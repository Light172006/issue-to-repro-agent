"""Deterministic stall detection over recorded tool steps; no model calls."""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from repro.matcher import extract_failure
from repro.parser import normalize_signature


@dataclass(frozen=True)
class StallVerdict:
    stalled: bool
    reason: str | None = None
    evidence: tuple[str, ...] = ()
    infrastructure: bool = False


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8', 'replace')).hexdigest()


def _error(step: dict[str, Any]) -> str | None:
    output = str(step.get('output') or '')
    failure = extract_failure(output)
    if failure:
        return '|'.join((failure.exception_type, failure.message or '', failure.frame or ''))
    error = step.get('error')
    if isinstance(error, str) and error:
        return normalize_signature('ToolError', error)
    return None


def _call(step: dict[str, Any]) -> str:
    return json.dumps([step.get('tool'), step.get('arguments', {})], sort_keys=True, ensure_ascii=True)


def _observations(step: dict[str, Any]) -> set[str]:
    observed = set()
    output = step.get('output')
    if isinstance(output, str) and output:
        observed.add('output:' + _hash(output))
    error = _error(step)
    if error:
        observed.add('error:' + error)
    args = step.get('arguments')
    if step.get('tool') == 'write_file' and isinstance(args, dict):
        content = args.get('content')
        if isinstance(content, str):
            observed.add('file:' + str(args.get('path')) + ':' + _hash(content))
    return observed


def detect_stall(history: list[dict[str, Any]], config: dict[str, Any]) -> StallVerdict:
    """Return evidence from steps only; no clocks, models, or mutable state."""
    steps = [item for item in history if isinstance(item, dict) and item.get('tool')]
    if len(steps) < int(config.get('min_steps', 4)):
        return StallVerdict(False)
    errors = [_error(step) for step in steps]
    threshold = max(2, int(config.get('repeat_error_threshold', 3)))
    recent = errors[-threshold:]
    if len(recent) == threshold and recent[0] and all(error == recent[0] for error in recent):
        text = ' '.join(str(step.get('output', '')) for step in steps[-threshold:])
        infra = bool(re.search(r'(?i)docker daemon|container (?:failed|error)|cannot connect to docker|'
                               r'no module named [\'\"](?:pytest|pip)[\'\"]|sandbox error', text))
        return StallVerdict(True, 'repeated_error', (recent[0], str(threshold)), infra)
    calls = [_call(step) for step in steps]
    if len(calls) >= threshold and len(set(calls[-threshold:])) == 1:
        return StallVerdict(True, 'repeated_tool_call', (_hash(calls[-1]), str(threshold)))
    if len(calls) >= 4 and calls[-4] == calls[-2] and calls[-3] == calls[-1] and calls[-1] != calls[-2]:
        return StallVerdict(True, 'oscillation', (_hash(calls[-2]), _hash(calls[-1])))
    no_progress = max(1, int(config.get('no_progress_steps', 5)))
    if len(steps) > no_progress:
        seen = set().union(*(_observations(step) for step in steps[:-no_progress]))
        new = set().union(*(_observations(step) for step in steps[-no_progress:]))
        if not new - seen:
            return StallVerdict(True, 'no_progress', (str(no_progress),))
    return StallVerdict(False)
