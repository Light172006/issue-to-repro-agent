"""Fetch and cache public GitHub issue reports. Issue content is untrusted."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

ISSUE_PATH = re.compile(r'^/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9_.-]+)/issues/([1-9][0-9]*)/?$')
LINK = re.compile(r'https?://[^\s<>\]\)"\']+')


class IssueFetchError(RuntimeError):
    """The issue cannot be fetched or is not a supported issue."""


def parse_issue_url(url: str) -> tuple[str, str, int]:
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc.lower() not in ('github.com', 'www.github.com')
                or parsed.query or parsed.fragment):
            raise ValueError
        match = ISSUE_PATH.fullmatch(parsed.path)
        if not match or match.group(2) in ('.', '..'):
            raise ValueError
        return match.group(1), match.group(2), int(match.group(3))
    except (ValueError, AttributeError):
        raise ValueError('Expected https://github.com/OWNER/REPO/issues/NUMBER') from None


def _get_json(client, url: str, *, params=None):
    try:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as exc:  # noqa: BLE001 - sanitize all client errors to avoid leaking tokens.
        # Avoid logging request headers or token-bearing exception text.
        status = getattr(getattr(exc, 'response', None), 'status_code', None)
        raise IssueFetchError(f'GitHub request failed (HTTP {status})' if status else 'GitHub request failed') from None


def fetch_issue(url: str, cache_dir: str | Path = '.cache/issues', *, token: str | None = None,
                refresh: bool = False, client=None) -> tuple[dict, Path]:
    """Return (issue, cache path); complete comment pages are saved atomically.

    When provided, ``client`` must be an httpx-compatible client. No content
    linked in the issue is fetched automatically.
    """
    owner, repo, number = parse_issue_url(url)
    cache_dir = Path(cache_dir)
    cache_key = hashlib.sha256(f'{owner.lower()}/{repo.lower()}#{number}'.encode()).hexdigest()
    cache_path = cache_dir / f'{cache_key}.json'
    if not refresh and cache_path.is_file():
        try:
            cached = json.loads(cache_path.read_text(encoding='utf-8'))
            if (cached.get('schema_version') == 2 and cached.get('repo', '').lower() == f'{owner}/{repo}'.lower()
                    and cached.get('number') == number and isinstance(cached.get('comments'), list)):
                return cached, cache_path
        except (OSError, ValueError, AttributeError):
            pass

    owned = client is None
    if owned:
        import httpx
        headers = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28',
                   'User-Agent': 'issue-to-repro-agent'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        client = httpx.Client(headers=headers, timeout=20, follow_redirects=False)
    try:
        base = f'https://api.github.com/repos/{owner}/{repo}/issues/{number}'
        issue = _get_json(client, base)
        if not isinstance(issue, dict) or 'pull_request' in issue:
            raise IssueFetchError('URL does not point to a GitHub issue')
        comments = []
        page = 1
        while True:
            batch = _get_json(client, base + '/comments', params={'per_page': 100, 'page': page})
            if not isinstance(batch, list):
                raise IssueFetchError('Unexpected comments response')
            comments.extend({'id': item.get('id'), 'author': (item.get('user') or {}).get('login'),
                             'author_type': (item.get('user') or {}).get('type'),
                             'body': item.get('body') or '', 'created_at': item.get('created_at'),
                             'updated_at': item.get('updated_at'), 'url': item.get('html_url')}
                            for item in batch)
            if len(batch) < 100:
                break
            page += 1
            if page > 100:
                raise IssueFetchError('Comment pagination limit exceeded')
        body = issue.get('body') or ''
        links = sorted(set(LINK.findall('\n'.join([body] + [c['body'] for c in comments]))))
        result = {'schema_version': 2, 'reporter': (issue.get('user') or {}).get('login'),
                  'reporter_type': (issue.get('user') or {}).get('type'), 'repo': f'{owner}/{repo}', 'number': number,
                  'url': f'https://github.com/{owner}/{repo}/issues/{number}',
                  'title': issue.get('title', ''), 'body': body,
                  'labels': [label['name'] for label in issue.get('labels', []) if isinstance(label, dict) and 'name' in label],
                  'comments': comments, 'linked_urls': links,
                  'fetched_at': datetime.now(UTC).isoformat()}
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=cache_dir, delete=False) as f:
                tmp = f.name
                json.dump(result, f, ensure_ascii=False, indent=2)
                f.write('\n')
            os.replace(tmp, cache_path)
            tmp = None
        finally:
            if tmp is not None:
                os.unlink(tmp)
        return result, cache_path
    finally:
        if owned:
            client.close()


def main():
    parser = argparse.ArgumentParser(description='Fetch and cache a GitHub issue')
    parser.add_argument('issue_url')
    parser.add_argument('--cache-dir', default='.cache/issues')
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    try:
        issue, path = fetch_issue(args.issue_url, args.cache_dir, token=os.getenv('GITHUB_TOKEN'), refresh=args.refresh)
    except (ValueError, IssueFetchError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')
    print(f"Saved {issue['repo']}#{issue['number']} to {path}")


if __name__ == '__main__':
    main()

