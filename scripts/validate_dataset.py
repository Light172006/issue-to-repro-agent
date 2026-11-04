"""Ground-truth validation for the evaluation benchmark dataset.

Validates that for each feasible candidate issue:
1. Environment builds successfully using the production EnvironmentBuilder.
2. The fix's test fails at the buggy commit with the reported symptom.
3. The fix's test passes at the fix commit (exit code 0).
4. Infeasible issues are validated for justification (evidence + valid category).
Rejected issues are recorded in bench/rejected.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import docker
import httpx

from repro.envbuilder import EnvironmentBuilder
from repro.matcher import DeterministicSymptomChecker
from repro.parser import IssueRecord, Symptom
from repro.sandbox import Sandbox

VALID_INFEASIBLE_CATEGORIES = {'hardware', 'os', 'network', 'credentials', 'external_service'}


def _load_env() -> None:
    env_file = Path('.env')
    if env_file.is_file():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip('\'"'))


def fetch_commit_file(repo: str, commit_sha: str, file_path: str, client: httpx.Client) -> str:
    """Fetch content of a file at a specific commit via GitHub raw or API."""
    url = f'https://raw.githubusercontent.com/{repo}/{commit_sha}/{file_path}'
    resp = client.get(url, timeout=20)
    if resp.status_code == 200:
        return resp.text
    # Fallback to API contents
    api_url = f'https://api.github.com/repos/{repo}/contents/{file_path}?ref={commit_sha}'
    resp = client.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    import base64
    return base64.b64decode(data['content']).decode('utf-8', errors='replace')


def validate_infeasible(candidate: dict[str, Any]) -> tuple[bool, str]:
    cat = candidate.get('category')
    if cat != 'infeasible':
        return False, 'Category is not infeasible'
    reason_cat = candidate.get('infeasible_category')
    if not reason_cat:
        reason_text = candidate.get('infeasible_reason', '').lower()
        title_text = candidate.get('title', '').lower()
        combined = f'{title_text} {reason_text}'
        if any(k in combined for k in ('network', 'dns', 'socket', 'internet')):
            reason_cat = 'network'
        elif any(k in combined for k in ('windows', 'win32', 'kernel32', 'os', 'macos', 'platform')):
            reason_cat = 'os'
        elif any(k in combined for k in ('hardware', 'gpu', 'cuda', 'nvml', 'tpu', 'device')):
            reason_cat = 'hardware'
        elif any(k in combined for k in ('credential', 'api key', 'auth', 'token')):
            reason_cat = 'credentials'
        elif any(k in combined for k in ('external service', 'private service')):
            reason_cat = 'external_service'
    if reason_cat not in VALID_INFEASIBLE_CATEGORIES:
        return False, f'Invalid infeasible category: {reason_cat} (allowed: {sorted(VALID_INFEASIBLE_CATEGORIES)})'
    reason = candidate.get('infeasible_reason', '')
    if not reason or len(reason.strip()) < 10:
        return False, 'Infeasible reason too short or missing'
    evidence = candidate.get('infeasible_evidence') or candidate.get('test_code') or reason
    if not evidence or len(str(evidence).strip()) < 10:
        return False, 'Infeasible evidence too short or missing'
    return True, f'Infeasible candidate validated (category: {reason_cat})'


def run_test_in_image(dc: docker.DockerClient, image: str, test_filename: str, test_code: str,
                      *, timeout: int = 60, run_id: str = 'test') -> tuple[int, str]:
    """Run test_code in Sandbox with image, writing test_code into mounted repro folder."""
    repro_dir = Path('runs') / f'val_{run_id}' / 'repro'
    repro_dir.mkdir(parents=True, exist_ok=True)
    try:
        test_file = repro_dir / test_filename
        test_file.write_text(test_code, encoding='utf-8')

        sb = Sandbox(image=image, client=dc, max_timeout=timeout,
                     working_dir='/var/tmp/repro/source',
                     writable_mount=repro_dir)
        cmd = ['/var/tmp/repro/venv/bin/pytest', '-v', f'/work/repro/{test_filename}']
        res = sb.run(cmd, timeout=timeout)
        code = 0 if res.exit_code is None else res.exit_code
        return code, res.output
    finally:
        if (repro_dir / test_filename).is_file():
            (repro_dir / test_filename).unlink(missing_ok=True)


def validate_candidate(candidate: dict[str, Any], dc: docker.DockerClient | None, hc: httpx.Client,
                       builder: EnvironmentBuilder | None, runs_dir: Path) -> tuple[bool, dict[str, Any], str]:
    cid = candidate['id']
    if candidate.get('category') == 'infeasible':
        ok, msg = validate_infeasible(candidate)
        if ok:
            return True, {'status': 'validated_infeasible', 'date': time.strftime('%Y-%m-%d')}, msg
        return False, {}, msg

    if dc is None or builder is None:
        return False, {}, 'Docker environment is required to validate feasible candidates'

    repo = candidate['library']
    buggy_ref = candidate['buggy_ref']
    fix_ref = candidate['fix_ref']
    test_file_path = candidate['test_file_path']
    test_code_snippet = candidate.get('test_code')

    # If test code not embedded, fetch from GitHub at fix_ref
    if not test_code_snippet:
        try:
            test_code_snippet = fetch_commit_file(repo, fix_ref, test_file_path, hc)
        except Exception as e:  # noqa: BLE001
            return False, {}, f'Failed to fetch test file {test_file_path} from fix {fix_ref}: {e}'

    # 1. Build buggy environment
    buggy_out = runs_dir / f'val_{cid}_buggy'
    try:
        buggy_meta = builder.build(repo, buggy_ref, buggy_out, timeout=300)
    except Exception as e:  # noqa: BLE001
        return False, {}, f'Buggy environment build failed: {e}'

    buggy_image = buggy_meta['image']
    buggy_baseline = buggy_meta.get('baseline', {'status': 'unavailable'})

    # 2. Run test in buggy environment (must fail with symptom match)
    test_filename = Path(test_file_path).name
    try:
        b_code, b_out = run_test_in_image(dc, buggy_image, test_filename, test_code_snippet, timeout=60, run_id=f'{cid}_buggy')
    except Exception as e:  # noqa: BLE001
        return False, {}, f'Test execution at buggy commit failed: {e}'

    if b_code == 0:
        return False, {}, f'Test passed at buggy commit {buggy_ref}; bug was not reproduced'

    # Check symptom match
    sym_data = candidate.get('symptom', {})
    record = IssueRecord(
        repo=repo,
        issue=candidate.get('issue_number', 1),
        symptom=Symptom(
            kind=sym_data.get('kind', 'exception'),
            type=sym_data.get('type'),
            signature=sym_data.get('signature'),
        ),
        expected=candidate.get('expected_behavior'),
        actual=candidate.get('actual_behavior')
    )
    checker = DeterministicSymptomChecker(baseline=buggy_baseline)
    match = checker.check(record, b_out)
    if match.verdict == 'none':
        return False, {}, f'Symptom mismatch at buggy commit: {match.reason}\nPytest output snippet:\n{b_out[:500]}'

    # 3. Build fix environment
    fix_out = runs_dir / f'val_{cid}_fix'
    try:
        fix_meta = builder.build(repo, fix_ref, fix_out, timeout=300)
    except Exception as e:  # noqa: BLE001
        return False, {}, f'Fix environment build failed: {e}'

    fix_image = fix_meta['image']
    fix_baseline = fix_meta.get('baseline', {'status': 'unavailable'})

    # 4. Run test in fix environment (must pass)
    try:
        f_code, f_out = run_test_in_image(dc, fix_image, test_filename, test_code_snippet, timeout=60, run_id=f'{cid}_fix')
    except Exception as e:  # noqa: BLE001
        return False, {}, f'Test execution at fix commit failed: {e}'

    if f_code != 0:
        return False, {}, f'Test failed at fix commit {fix_ref} (exit {f_code})\nOutput snippet:\n{f_out[:500]}'

    val_record = {
        'status': 'passed',
        'buggy_ref': buggy_ref,
        'fix_ref': fix_ref,
        'buggy_exit_code': b_code,
        'buggy_symptom_match': match.verdict,
        'fix_exit_code': f_code,
        'buggy_baseline': buggy_baseline.get('counts'),
        'fix_baseline': fix_baseline.get('counts'),
        'date': time.strftime('%Y-%m-%d')
    }
    return True, val_record, 'Validated'


def main() -> int:
    parser = argparse.ArgumentParser(description='Ground-truth benchmark validator')
    parser.add_argument('--input', default=None, help='Path to candidate issues JSON (defaults to bench/dataset.json)')
    parser.add_argument('--candidate', default=None, help='Specific candidate ID to validate')
    parser.add_argument('--output', default='bench/dataset.json', help='Output validated dataset JSON')
    parser.add_argument('--rejected', default='bench/rejected.json', help='Output rejected issues JSON')
    args = parser.parse_args()

    _load_env()
    token = os.environ.get('GITHUB_TOKEN')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
    if token:
        headers['Authorization'] = 'Bearer ' + token

    input_file = args.input or ('bench/dataset.json' if Path('bench/dataset.json').is_file() else 'bench/candidates.json')
    input_path = Path(input_file)
    if not input_path.is_file():
        print(f'Error: input file {input_path} does not exist', file=sys.stderr)
        return 1

    candidates = json.loads(input_path.read_text(encoding='utf-8'))
    if args.candidate:
        candidates = [c for c in candidates if c.get('id') == args.candidate]
        if not candidates:
            print(f'Error: candidate {args.candidate} not found in {input_path}', file=sys.stderr)
            return 1
    print(f'Loaded {len(candidates)} candidate(s) from {input_path}')

    dc: docker.DockerClient | None = None
    builder: EnvironmentBuilder | None = None
    hc = httpx.Client(headers=headers, timeout=20)
    runs_dir = Path('runs/validation')
    runs_dir.mkdir(parents=True, exist_ok=True)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    try:
        for c in candidates:
            cid = c.get('id', 'unknown')
            print(f'Validating candidate: {cid} ({c.get("library")} #{c.get("issue_number")})...')
            if c.get('category') != 'infeasible' and dc is None:
                dc = docker.from_env()
                builder = EnvironmentBuilder(dc, hc)
            ok, val_meta, reason = validate_candidate(c, dc, hc, builder, runs_dir)
            if ok:
                print(f'  [ACCEPTED] {cid}: {reason}')
                c['validation'] = val_meta
                accepted.append(c)
            else:
                print(f'  [REJECTED] {cid}: {reason}')
                rejected.append({'id': cid, 'library': c.get('library'), 'issue_number': c.get('issue_number'),
                                 'reason': reason, 'date': time.strftime('%Y-%m-%d')})
    finally:
        hc.close()
        if dc is not None:
            dc.close()

    if not args.candidate:
        Path(args.output).write_text(json.dumps(accepted, indent=2) + '\n', encoding='utf-8')
        Path(args.rejected).write_text(json.dumps(rejected, indent=2) + '\n', encoding='utf-8')
    print(f'Done: {len(accepted)} accepted, {len(rejected)} rejected.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
