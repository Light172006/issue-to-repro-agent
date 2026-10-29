"""Independent, model-free verification of saved reproduction tests."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import time
from pathlib import Path

from repro.matcher import DeterministicSymptomChecker, extract_failure
from repro.parser import IssueRecord
from repro.result_writer import _atomic_write
from repro.sandbox import Sandbox

_PASSED = re.compile(r'\b([1-9]\d*) passed\b')


def _fingerprint(issue: IssueRecord, output: str) -> tuple | None:
    if issue.symptom.kind == 'exception':
        failure = extract_failure(output)
        if failure and failure.message and failure.frame:
            return (failure.exception_type, failure.message, failure.frame)
    if issue.symptom.kind == 'wrong_output':
        # Exact output matching is already checked against the issue by the matcher.
        return ('wrong_output', issue.actual, issue.expected)
    return None


def _run_once(client, image: str, candidate: bytes, *, runs: Path, timeout: float):
    """Run immutable input in a fresh writable mount and disposable container."""
    runs.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix='verify-', dir=runs))
    try:
        mount = temporary / 'repro'
        mount.mkdir()
        (mount / 'test_repro.py').write_bytes(candidate)
        with Sandbox(image=image, client=client, working_dir='/var/tmp/repro/source',
                     writable_mount=mount, max_timeout=timeout) as sandbox:
            return sandbox.run(['/var/tmp/repro/venv/bin/python', '-m', 'pytest',
                                '-p', 'no:cacheprovider', '/work/repro/test_repro.py'],
                               timeout=timeout)
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


def verify(issue: IssueRecord, candidate: bytes, buggy_image: str, client, *,
           runs: Path, fixed_image: str | None = None, fixed_ref: str | None = None,
           timeout: float = 60, deadline: float | None = None, runner=_run_once) -> dict:
    """Run five independent checks and optionally compare a fixed image.

    A fixed image must be selected by the caller; it is never inferred from a
    model's claim. The caller is responsible for checking that it differs from
    the buggy commit. A failed/inconclusive fixed check cannot establish high
    or medium confidence.
    """
    if not candidate or len(candidate) > 65536:
        raise ValueError('Candidate must be nonempty and at most 65536 bytes')
    checker = DeterministicSymptomChecker()
    observations = []
    fingerprints = []
    for _ in range(5):
        remaining = timeout if deadline is None else min(timeout, deadline - time.monotonic())
        if remaining <= 0:
            observations.append({'error': 'time limit reached'})
            break
        try:
            result = runner(client, buggy_image, candidate, runs=runs, timeout=remaining)
            match = checker.check(issue, result.output) if result.exit_code == 1 and not result.timed_out else None
            fingerprint = _fingerprint(issue, result.output) if match and match.verdict != 'none' else None
            observations.append({'exit_code': result.exit_code, 'timed_out': result.timed_out,
                                 'verdict': match.verdict if match else 'none',
                                 'failure': list(fingerprint) if fingerprint else None})
            fingerprints.append(fingerprint)
        except Exception as exc:  # noqa: BLE001 - verification failures are evidence, not success.
            observations.append({'error': type(exc).__name__})
            fingerprints.append(None)
    matches = [o.get('verdict') for o in observations]
    any_match = any(v in ('exact', 'partial') for v in matches)
    same = (len(observations) == 5 and len(fingerprints) == 5 and
            fingerprints[0] is not None and all(f == fingerprints[0] for f in fingerprints) and
            all(v in ('exact', 'partial') for v in matches))
    exact = same and all(v == 'exact' for v in matches)
    fixed = None
    if fixed_image is not None and any_match:
        fixed = {'ref': fixed_ref, 'passed': False}
        remaining = timeout if deadline is None else min(timeout, deadline - time.monotonic())
        if remaining <= 0:
            fixed['error'] = 'time limit reached'
        else:
            try:
                result = runner(client, fixed_image, candidate, runs=runs, timeout=remaining)
                fixed.update({'exit_code': result.exit_code, 'timed_out': result.timed_out,
                              'passed': result.exit_code == 0 and not result.timed_out and
                                        bool(_PASSED.search(result.output))})
            except Exception as exc:  # noqa: BLE001
                fixed['error'] = type(exc).__name__
    if not any_match:
        confidence = None
    elif not exact:
        confidence = 'low'
    elif fixed is None:
        confidence = 'medium'
    elif fixed['passed']:
        confidence = 'high'
    else:
        confidence = 'low'
    # A failing fixed-version check is not a verified reproduction.
    reproduced = same and (fixed is None or fixed['passed'])
    return {'status': 'reproduced' if reproduced else 'not_reproduced',
            'confidence': confidence, 'verification': 'completed',
            'checks': {'symptom_match': 'exact' if exact else 'partial' if any_match else 'none',
                       'repeated_runs': {'consistent': same, 'runs': observations},
                       'fixed_version': fixed},
            'candidate_sha256': hashlib.sha256(candidate).hexdigest()}


def save_verification(folder: Path, verification: dict) -> dict:
    """Atomically update the existing result without changing the candidate."""
    path = folder / 'result.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    data.update(verification)
    data['status_detail'] = ('Independent verification passed' if data['status'] == 'reproduced'
                             else 'Independent verification did not pass')
    _atomic_write(path, (json.dumps(data, indent=2) + '\n').encode('utf-8'))
    return data
