"""Conservative, deterministic recording and comparison of baseline failures."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from repro.matcher import extract_failure

_SUMMARY = re.compile(r'^=+\s*([^\n]*\b(?:passed|failed|skipped|errors?)\b[^\n]*)=+\s*$', re.MULTILINE)
_COUNT = re.compile(r'\b(\d+)\s+(passed|failed|skipped|errors?)\b')
_FAILED = re.compile(r'^FAILED\s+(\S+)', re.MULTILINE)
_HEADER = re.compile(r'^_+\s+(.+?)\s+_+\s*$', re.MULTILINE)


def _signature(output: str) -> str | None:
    failure = extract_failure(output)
    if not failure or not failure.message or not failure.frame:
        return None
    # Persist only a digest, so exception messages cannot leak secrets to metadata.
    normalized = json.dumps([failure.exception_type, failure.message, failure.frame], ensure_ascii=True)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def baseline_from_result(result) -> dict:
    """Classify pytest output without treating incomplete evidence as a clean suite."""
    base = {'status': 'runner_error', 'counts': None, 'failures': []}
    if result.timed_out:
        return {**base, 'status': 'timeout'}
    output = result.output
    if '... output truncated:' in output or (result.original_length is not None and
            result.original_length > len(output.encode('utf-8'))):
        return {**base, 'status': 'truncated'}
    if result.exit_code == 2:
        return {**base, 'status': 'collection_error'}
    summaries = list(_SUMMARY.finditer(output))
    if not summaries:
        return base
    counts = {'passed': 0, 'failed': 0, 'skipped': 0}
    errors = 0
    for number, name in _COUNT.findall(summaries[-1].group(1)):
        if name.startswith('error'):
            errors += int(number)
        else:
            counts[name] += int(number)
    if errors:
        return {**base, 'status': 'collection_error'}
    if result.exit_code not in (0, 1):
        return base
    if not counts['passed'] and not counts['failed']:
        return {**base, 'status': 'no_tests'}
    ids = _FAILED.findall(output)
    if (len(ids) != counts['failed'] or len(set(ids)) != len(ids) or
            (result.exit_code == 1) != (counts['failed'] > 0)):
        return {**base, 'status': 'incomplete'}
    headers = list(_HEADER.finditer(output))
    failures = []
    for test in ids:
        matches = [h for h in headers if h.group(1).split('::')[-1] == test.split('::')[-1]]
        if len(matches) != 1:
            return {'status': 'incomplete', 'counts': counts, 'failures': [
                {'test': name, 'pre_existing': True, 'signature': None} for name in ids]}
        index = headers.index(matches[0])
        section = output[matches[0].start():headers[index + 1].start() if index + 1 < len(headers) else len(output)]
        signature = _signature(section)
        if signature is None:
            return {'status': 'incomplete', 'counts': counts, 'failures': [
                {'test': name, 'pre_existing': True, 'signature': None} for name in ids]}
        failures.append({'test': test, 'pre_existing': True, 'signature': signature})
    return {'status': 'complete', 'counts': counts, 'failures': failures}


def load_baseline(path: Path) -> dict:
    try:
        metadata = json.loads(path.read_text(encoding='utf-8'))
        baseline = metadata['baseline']
        if not isinstance(baseline, dict):
            raise TypeError('Invalid baseline')
        return baseline
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'unavailable', 'counts': None, 'failures': []}


def baseline_rejection(baseline: dict, output: str) -> str | None:
    if not isinstance(baseline, dict) or baseline.get('status') != 'complete':
        return 'Baseline unavailable or inconclusive'
    failures = baseline.get('failures')
    counts = baseline.get('counts')
    if (not isinstance(failures, list) or not isinstance(counts, dict) or
            any(type(counts.get(k)) is not int or counts[k] < 0 for k in ('passed', 'failed', 'skipped')) or
            len(failures) != counts['failed']):
        return 'Baseline metadata invalid'
    observed_ids = set(_FAILED.findall(output))
    headers = list(_HEADER.finditer(output))
    signatures = [_signature(output[h.start():headers[i + 1].start() if i + 1 < len(headers) else len(output)])
                  for i, h in enumerate(headers)]
    if not headers:
        signatures = [_signature(output)]
    for failure in failures:
        if (not isinstance(failure, dict) or failure.get('pre_existing') is not True or
                not isinstance(failure.get('test'), str) or
                not isinstance(failure.get('signature'), str) or
                not re.fullmatch(r'[0-9a-f]{64}', failure['signature'])):
            return 'Baseline metadata invalid'
        if failure['test'] in observed_ids or failure['signature'] in signatures:
            return 'Failure matches a pre-existing baseline failure'
    if failures and (not signatures or any(signature is None for signature in signatures)):
        return 'Cannot compare candidate against baseline signatures'
    return None
