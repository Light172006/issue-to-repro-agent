"""Fetch and sanitize issue snapshots for accepted benchmark issues.

Saves issue body and first 10 reporter comments to bench/snapshots/<id>.json.
Strips maintainer solution hints or pull request references to prevent contamination.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

_MAINTAINER_ROLES = {'MEMBER', 'COLLABORATOR', 'OWNER'}
_PR_LINK_RE = re.compile(r'https?://github\.com/[^/\s]+/[^/\s]+/pull/\d+|#\d{2,6}\b')
_COMMIT_HASH_RE = re.compile(r'\b[0-9a-f]{40}\b')


def _load_env() -> None:
    env_file = Path('.env')
    if env_file.is_file():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip('\'"'))


def sanitize_text(text: str) -> str:
    if not text:
        return ''
    # Strip explicit PR links or commit SHAs to prevent fix leakage
    text = _PR_LINK_RE.sub('[LINK_REMOVED]', text)
    text = _COMMIT_HASH_RE.sub('[COMMIT_REMOVED]', text)
    return text


def fetch_snapshot(issue_url: str, library: str, issue_number: int, client: httpx.Client) -> dict[str, Any]:
    api_url = f'https://api.github.com/repos/{library}/issues/{issue_number}'
    resp = client.get(api_url, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    reporter = data.get('user', {}).get('login', 'reporter')
    reporter_type = data.get('user', {}).get('type', 'User')
    raw_body = data.get('body') or ''
    sanitized_body = sanitize_text(raw_body)

    # Fetch comments
    comments_url = f'{api_url}/comments'
    comments_resp = client.get(comments_url, params={'per_page': 50}, timeout=20)
    raw_comments = comments_resp.json() if comments_resp.status_code == 200 else []

    kept_comments = []
    for c in raw_comments:
        user = c.get('user', {}).get('login')
        role = c.get('author_association', 'NONE')
        body = c.get('body', '')

        # Strip maintainer comments that give away solution or link to fixes
        if role in _MAINTAINER_ROLES:
            continue
        # Also skip if body contains explicit solution announcements
        lower = body.lower()
        if 'fixed in #' in lower or 'closed in #' in lower or 'pr merged' in lower:
            continue

        kept_comments.append({
            'user': user,
            'author_association': role,
            'body': sanitize_text(body)
        })
        if len(kept_comments) >= 10:
            break

    return {
        'schema_version': 2,
        'repo': library,
        'number': issue_number,
        'reporter': reporter,
        'reporter_type': reporter_type,
        'body': sanitized_body,
        'comments': kept_comments
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate snapshots for accepted benchmark issues')
    parser.add_argument('--dataset', default='bench/dataset.json', help='Path to validated dataset JSON')
    parser.add_argument('--output-dir', default='bench/snapshots', help='Directory to save snapshots')
    args = parser.parse_args()

    _load_env()
    token = os.environ.get('GITHUB_TOKEN')
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
    if token:
        headers['Authorization'] = 'Bearer ' + token

    dataset_path = Path(args.dataset)
    if not dataset_path.is_file():
        print(f'Error: dataset {dataset_path} not found')
        return 1

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    issues = json.loads(dataset_path.read_text(encoding='utf-8'))
    with httpx.Client(headers=headers) as client:
        for item in issues:
            cid = item['id']
            lib = item['library']
            num = item['issue_number']
            url = item['issue_url']
            print(f'Fetching snapshot for {cid} ({lib} #{num})...')
            snap = fetch_snapshot(url, lib, num, client)
            snap_file = out_dir / f'{cid}.json'
            snap_file.write_text(json.dumps(snap, indent=2, ensure_ascii=False), encoding='utf-8')
            print(f'Saved {snap_file}')

    return 0


if __name__ == '__main__':
    sys.exit(main())
