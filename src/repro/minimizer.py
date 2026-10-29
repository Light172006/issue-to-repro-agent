"""Syntax-aware source ranges for deterministic reproduction reduction."""
from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    start: int
    end: int
    replacement: str = ''


def units(source: str, *, top_level: bool) -> list[Unit]:
    """Return removable statement line ranges without regenerating source."""
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    result = []
    if top_level:
        bodies = [tree.body]
    else:
        bodies = []
        seen = set()
        for function in (node for node in ast.walk(tree)
                         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            for node in ast.walk(function):
                for _, value in ast.iter_fields(node):
                    if (isinstance(value, list) and value and
                            all(isinstance(item, ast.stmt) for item in value) and id(value) not in seen):
                        seen.add(id(value))
                        bodies.append(value)
    for body in bodies:
        for statement in body:
            start = min([statement.lineno] + [d.lineno for d in getattr(statement, 'decorator_list', [])])
            end = statement.end_lineno or statement.lineno
            replacement = ''
            if len(body) == 1 and not top_level:
                indent = lines[statement.lineno - 1][:statement.col_offset]
                newline = '\r\n' if lines[statement.lineno - 1].endswith('\r\n') else '\n'
                replacement = indent + 'pass' + newline
            result.append(Unit(start, end, replacement))
    return sorted(result, key=lambda u: (u.start, u.end))


def remove_units(source: str, selected: list[Unit]) -> str:
    lines = source.splitlines(keepends=True)
    for unit in sorted(selected, key=lambda u: u.start, reverse=True):
        lines[unit.start - 1:unit.end] = [unit.replacement] if unit.replacement else []
    return ''.join(lines)

import hashlib
import math
import time
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

from repro.verifier import _fingerprint


@dataclass(frozen=True)
class MinimizeResult:
    status: str
    original_lines: int
    final_lines: int
    runs: int
    duration_s: float
    source: bytes


def line_count(source: str) -> int:
    return sum(bool(line.strip()) and not line.lstrip().startswith('#') for line in source.splitlines())


def _ddmin(source: str, choices: Callable[[str], list[Unit]], accept: Callable[[str], bool]) -> str:
    """Deterministic chunk reduction followed by single-statement checks."""
    granularity = 2
    while True:
        options = choices(source)
        if not options:
            return source
        width = max(1, math.ceil(len(options) / granularity))
        changed = False
        for index in range(0, len(options), width):
            selected = options[index:index + width]
            # Overlapping parent and child ranges are tried separately.
            if any(a.end >= b.start for a, b in pairwise(selected)):
                continue
            candidate = remove_units(source, selected)
            if candidate != source and accept(candidate):
                source = candidate
                granularity = max(2, granularity - 1)
                changed = True
                break
        if not changed:
            if width == 1:
                return source
            granularity = min(len(options), granularity * 2)


def minimize(repro_path, record, runner, matcher, limits) -> MinimizeResult:
    """Reduce a verified pytest candidate. runner accepts bytes and timeout.

    The caller must independently verify the returned candidate before saving it.
    """
    start = time.monotonic()
    path = Path(repro_path)
    raw = path.read_bytes()
    try:
        source = raw.decode('utf-8')
        compile(source, str(path), 'exec')
    except (UnicodeDecodeError, SyntaxError, ValueError):
        return MinimizeResult('skipped', 0, 0, 0, time.monotonic() - start, raw)
    original_lines = line_count(source)
    max_runs = int(limits.get('max_runs', 100))
    deadline = start + float(limits.get('time_limit_s', 300))
    timeout = max(10.0, float(limits.get('candidate_timeout_s', 10)))
    trace = limits.get('trace')
    runs = 0
    exhausted = False
    cache = {}

    def evaluate(text, original=False):
        nonlocal runs, exhausted
        key = hashlib.sha256(text.encode('utf-8')).hexdigest()
        if key in cache:
            return cache[key]
        try:
            compile(text, 'test_repro.py', 'exec')
        except (SyntaxError, ValueError):
            result = (False, 'syntax', None, None)
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or runs >= max_runs:
                exhausted = True
                return (False, 'limit', None, None)
            runs += 1
            try:
                observation = runner(text.encode('utf-8'), min(timeout, remaining))
                output = observation.output
                if observation.timed_out:
                    result = (False, 'timeout', None, None)
                elif observation.exit_code == 0:
                    result = (False, 'passes', None, None)
                elif observation.exit_code != 1 or ('ERROR collecting' in output or
                        'short test summary info' not in output or 'FAILED ' not in output):
                    result = (False, 'collection error', None, None)
                else:
                    verdict = matcher.check(record, output).verdict
                    signature = _fingerprint(record, output)
                    result = (verdict in ('exact', 'partial') and signature is not None,
                              'observed', verdict, signature)
            except Exception:  # noqa: BLE001 - fail closed for runner errors.
                result = (False, 'runner error', None, None)
        cache[key] = result
        if trace is not None and original:
            trace.write({'sha256': key, 'reason': result[1], 'baseline': True})
        return result

    baseline = evaluate(source, original=True)
    if not baseline[0]:
        return MinimizeResult('skipped', original_lines, original_lines, runs, time.monotonic() - start, raw)

    def accept(text):
        result = evaluate(text)
        accepted = result[0] and result[2:] == baseline[2:]
        if trace is not None:
            trace.write({'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),
                         'decision': 'accepted' if accepted else 'rejected',
                         'reason': 'same signature' if accepted else
                         'different signature' if result[0] else result[1]})
        return accepted

    source = _ddmin(source, lambda s: units(s, top_level=True), accept)
    source = _ddmin(source, lambda s: units(s, top_level=False), accept)
    source = _ddmin(source, lambda s: [Unit(i, i) for i, _ in enumerate(s.splitlines(), 1)], accept)
    # A final single-unit pass restores 1-minimality after line deletions.
    source = _ddmin(source, lambda s: units(s, top_level=True), accept)
    source = _ddmin(source, lambda s: units(s, top_level=False), accept)
    header = '# Minimized from test_repro.orig.py' + ('\r\n' if '\r\n' in source else '\n')
    if source != raw.decode('utf-8') and accept(header + source):
        source = header + source
    status = 'timeout' if exhausted else 'minimized' if source != raw.decode('utf-8') else 'unchanged'
    return MinimizeResult(status, original_lines, line_count(source), runs,
                          time.monotonic() - start, source.encode('utf-8'))


def minimize_run(folder, record, client, buggy_image, *, fixed_image=None,
                 fixed_ref=None, config=None, enabled=True, deadline=None):
    """Minimize an already verified run, reverify, and atomically save evidence."""
    import json
    from dataclasses import asdict

    from repro.matcher import DeterministicSymptomChecker
    from repro.result_writer import _atomic_write
    from repro.trace import TraceWriter
    from repro.verifier import _run_once, verify

    folder = Path(folder)
    result_path = folder / 'result.json'
    data = json.loads(result_path.read_text(encoding='utf-8'))
    candidate_path = folder / 'test_repro.py'
    if not enabled or data.get('status') != 'reproduced' or data.get('verification') != 'completed':
        data['minimization'] = {'status': 'skipped', 'original_lines': None, 'final_lines': None,
                                'runs': 0, 'duration_s': 0}
        _atomic_write(result_path, (json.dumps(data, indent=2) + '\n').encode())
        return data
    if candidate_path.is_symlink() or not candidate_path.is_file():
        raise ValueError('Candidate missing or is a symlink')
    original = candidate_path.read_bytes()
    backup = folder / 'test_repro.orig.py'
    if backup.is_symlink() or (backup.exists() and backup.read_bytes() != original):
        raise ValueError('Existing original backup differs from candidate')
    previous = data.get('checks', {}).get('repeated_runs', {}).get('runs', [])
    expected = previous[0].get('failure') if previous else None
    if not expected or hashlib.sha256(original).hexdigest() != data.get('candidate_sha256'):
        raise ValueError('Candidate does not match prior verification')
    old_fixed = data.get('checks', {}).get('fixed_version')
    if old_fixed and not fixed_image:
        raise ValueError('Fixed image required to preserve prior verification')
    _atomic_write(folder / 'test_repro.orig.py', original)
    settings = dict(config or {})
    if settings.get('workers', 1) != 1:
        raise ValueError('Only one minimizer worker is currently supported')
    settings['trace'] = TraceWriter(folder / 'minimize.jsonl')
    started = time.monotonic()
    local_deadline = started + float(settings.get('time_limit_s', 300))
    if deadline is not None:
        local_deadline = min(local_deadline, deadline)
        settings['time_limit_s'] = max(0, local_deadline - started)
    runner = lambda source, timeout: _run_once(client, buggy_image, source, runs=folder.parent, timeout=timeout)
    reduced = minimize(candidate_path, record, runner, DeterministicSymptomChecker(), settings)
    details = {k: v for k, v in asdict(reduced).items() if k != 'source'}
    verification = None
    if reduced.status != 'skipped':
        verification = verify(record, reduced.source, buggy_image, client, runs=folder.parent,
                              fixed_image=fixed_image, fixed_ref=fixed_ref,
                              deadline=local_deadline)
        ranks = {None: 0, 'low': 1, 'medium': 2, 'high': 3}
        final_runs = verification['checks']['repeated_runs']['runs']
        valid = (verification['status'] == 'reproduced' and
                 ranks[verification['confidence']] >= ranks.get(data.get('confidence'), 0) and
                 all(run.get('failure') == expected for run in final_runs))
        if valid:
            if reduced.source != original:
                _atomic_write(candidate_path, reduced.source)
            data.update(verification)
        else:
            details['status'] = 'failed_verification'
            details['final_lines'] = details['original_lines']
    data['minimization'] = details
    if verification is not None:
        data['minimization']['final_verification'] = verification
    _atomic_write(result_path, (json.dumps(data, indent=2) + '\n').encode('utf-8'))
    return data
