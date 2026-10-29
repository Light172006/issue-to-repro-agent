"""Verify four documented issue reproductions without model calls.

Each case is a hand-written test based on its public issue, not an agent run.
The script builds isolated images and records the observations for review.
"""
from __future__ import annotations

import json
import os
import uuid
from contextlib import closing
from pathlib import Path

import docker
import httpx

from repro.envbuilder import EnvironmentBuilder
from repro.parser import IssueRecord, Symptom, normalize_signature
from repro.verifier import verify

# Candidate versions without a reporter-provided version are explicitly pinned;
# they only count if the offline replay actually shows the reported failure.
CASES = [
    {
        'issue': 153, 'buggy': '4.8.0', 'fixed': '4.9.0',
        'error': 'AttributeError', 'message': "'NoneType' object has no attribute 'c'",
        'frame': 'helpers.py:base_set',
        'test': '''import pydash\n\ndef test_escaped_dot():\n    result = pydash.set_({'a': {'b.0': {}}}, r'a.b\\.0.c', 42)\n    assert result == {'a': {'b.0': {'c': 42}}}\n''',
    },
    {
        'issue': 147, 'buggy': '4.9.0',
        'fixed': 'cb1d35baff12015e7f0ba7a2ac519d332585292f',
        'error': 'TypeError', 'message': '__call__() takes 2 positional arguments but 3 were given',
        'frame': 'helpers.py:callit',
        'test': '''import pydash\n\nclass Filter:\n    def __init__(self, num):\n        self.num = num\n    def __call__(self, i):\n        return i > self.num\n\ndef test_callable():\n    assert pydash.find([0, 1, 2], Filter(1)) == 2\n''',
    },
    {
        'issue': 142, 'buggy': '1b4b425cecca275b8ba4c0584b40f9adae1cc097',
        'fixed': '7aed6751e9604bffdae9673a5dbb1c641dcaea3d',
        'error': 'TypeError', 'message': "'>' not supported between instances of 'NoneType' and 'NoneType'",
        'frame': '_compat.py:_cmp',
        'test': '''import pydash as py_\n\ndef test_order_by():\n    assert py_.order_by([{'value': 1}, {'value': 2}], 'value') == [{'value': 1}, {'value': 2}]\n''',
    },
    {
        'issue': 236, 'buggy': '8.0.4', 'fixed': '8.0.5',
        'error': 'TypeError', 'message': 'ServiceA.get() takes 2 positional arguments but 3 were given',
        'frame': 'helpers.py:callit',
        'test': '''from pydash import _\n\nclass ServiceA:\n    def get(self, id, **kwargs):\n        return id * 2\n\nclass ServiceB:\n    def __init__(self, service_a):\n        self.service_a = service_a\n    def all(self, models):\n        return _.map(models, self.service_a.get)\n\ndef test_all():\n    assert ServiceB(ServiceA()).all([1, 2, 3, 4, 5]) == [2, 4, 6, 8, 10]\n''',
    },
]


def main() -> int:
    runs = Path.cwd() / 'runs'
    runs.mkdir(exist_ok=True)
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
    if os.environ.get('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    failed = False
    with closing(docker.from_env()) as dc, httpx.Client(headers=headers, timeout=20) as hc:
        builder = EnvironmentBuilder(dc, hc)
        for case in CASES:
            folder = runs / f"step9-{case['issue']}-{uuid.uuid4().hex[:8]}"
            folder.mkdir()
            print(f"\nIssue: https://github.com/dgilland/pydash/issues/{case['issue']}", flush=True)
            try:
                issue = IssueRecord(repo='dgilland/pydash', issue=case['issue'],
                    symptom=Symptom(kind='exception', type=case['error'],
                        signature=normalize_signature(case['error'], case['message']) + ' @ ' + case['frame']))
                candidate = case['test'].encode('utf-8')
                (folder / 'test_repro.py').write_bytes(candidate)
                buggy = builder.build(issue.repo, case['buggy'], folder / 'buggy_environment')
                fixed = builder.build(issue.repo, case['fixed'], folder / 'fixed_environment')
                if buggy['commit'] == fixed['commit']:
                    raise ValueError('Buggy and fixed references resolve to the same commit')
                result = verify(issue, candidate, buggy['image'], dc, runs=runs,
                                fixed_image=fixed['image'], fixed_ref=fixed['selected_ref'])
                result.update({'issue_url': f'https://github.com/{issue.repo}/issues/{issue.issue}',
                               'buggy_commit': buggy['commit'], 'fixed_commit': fixed['commit'],
                               'source': 'hand-written from issue; not agent-generated'})
                (folder / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
                print(json.dumps(result, indent=2), flush=True)
                print(f'Evidence: {folder}', flush=True)
                if result['status'] != 'reproduced' or not result['checks']['fixed_version']['passed']:
                    failed = True
            except Exception as exc:  # noqa: BLE001 - keep remaining cases runnable.
                failed = True
                print(f'Case could not be verified: {type(exc).__name__}', flush=True)
                print(f'Evidence: {folder}', flush=True)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
