"""Replay a saved candidate without using a model or spending API credits."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from contextlib import closing
from pathlib import Path

import docker
import httpx

from repro.envbuilder import EnvironmentBuilder
from repro.parser import IssueRecord
from repro.verifier import save_verification, verify


def _version(value: str | None) -> tuple[int, ...] | None:
    if not isinstance(value, str) or not re.fullmatch(r'v?\d+(?:\.\d+)+', value):
        return None
    return tuple(int(part) for part in value.lstrip('v').split('.'))


def find_later_release(client, repo: str, version: str | None) -> str | None:
    """Find the first later numeric stable GitHub release; no fix is assumed."""
    current = _version(version)
    if current is None:
        return None
    response = client.get(f'https://api.github.com/repos/{repo}/releases',
                          params={'per_page': 100}, timeout=20, follow_redirects=False)
    response.raise_for_status()
    candidates = []
    for release in response.json():
        if not isinstance(release, dict) or release.get('draft') or release.get('prerelease'):
            continue
        tag = release.get('tag_name')
        parsed = _version(tag)
        if parsed is not None and parsed > current:
            candidates.append((parsed, tag))
    return min(candidates)[1] if candidates else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_folder', type=Path)
    parser.add_argument('--fixed-version', help='Known fixed tag or commit (optional)')
    parser.add_argument('--find-release', action='store_true', help='Try the first later stable GitHub release')
    args = parser.parse_args()
    try:
        folder = args.run_folder
        result = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
        if result.get('outcome') != 'candidate_found' or result.get('test_file') != 'test_repro.py':
            raise ValueError('Run has no saved candidate')
        file = folder / 'test_repro.py'
        if file.is_symlink() or not file.is_file():
            raise ValueError('Candidate is missing or is a symlink')
        candidate = file.read_bytes()
        events = [json.loads(line) for line in (folder / 'parser_trace.jsonl').read_text(encoding='utf-8').splitlines()]
        parsed = [event for event in events if event.get('event') == 'parser_result']
        if not parsed or parsed[-1].get('fallback') is not False:
            raise ValueError('Run has no validated parsed issue')
        issue = IssueRecord.model_validate(parsed[-1]['record'])
        env = json.loads((folder / 'environment.json').read_text(encoding='utf-8'))
        if env['repo'].lower() != issue.repo.lower():
            raise ValueError('Issue and environment repositories differ')
        fixed = None
        deadline = time.monotonic() + 900
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
        if os.environ.get('GITHUB_TOKEN'):
            headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
        with closing(docker.from_env()) as dc, httpx.Client(headers=headers, timeout=20) as hc:
            selected = args.fixed_version
            if args.find_release and not selected:
                selected = find_later_release(hc, issue.repo, issue.version)
                print(f'Later release: {selected or "none found"}')
            if selected:
                old_version, new_version = _version(issue.version), _version(selected)
                if old_version is not None and new_version is not None and new_version <= old_version:
                    raise ValueError('Fixed version must be later than the reported version')
                fixed = EnvironmentBuilder(dc, hc).build(issue.repo, selected,
                    folder / 'fixed_environment', timeout=max(1, min(600, int(deadline - time.monotonic()))),
                    test_dependencies=env.get('test_dependencies', []))
                if fixed['commit'] == env['commit']:
                    raise ValueError('Fixed and buggy versions resolve to the same commit')
            checks = verify(issue, candidate, env['image'], dc, runs=folder.parent,
                            fixed_image=fixed['image'] if fixed else None,
                            fixed_ref=fixed['selected_ref'] if fixed else None, deadline=deadline,
                            baseline=env.get('baseline'))
            if fixed:
                checks['checks']['fixed_version']['commit'] = fixed['commit']
            saved = save_verification(folder, checks)
        print(f"Status: {saved['status']}; confidence: {saved['confidence']}")
        print(json.dumps(saved['checks'], indent=2))
        print(f"Updated: {folder / 'result.json'}")
        return 0 if saved['status'] == 'reproduced' else 1
    except Exception as exc:  # noqa: BLE001 - don't expose credentials from errors.
        print(f'Verification failed: {type(exc).__name__}: {str(exc) if isinstance(exc, ValueError) else "see setup and Docker availability"}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
