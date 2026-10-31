"""Build reusable Docker images for public Python GitHub projects."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import time
from contextlib import closing
from pathlib import Path

from repro.baseline import baseline_from_result
from repro.github import parse_issue_url
from repro.sandbox import Sandbox, _is_wait_timeout

SHA = re.compile(r'^[0-9a-f]{40}$')
TAG = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,100}$')

class BuildError(RuntimeError):
    pass


def resolve_commit(repo: str, version: str | None, client) -> tuple[str, str]:
    """Resolve a GitHub version as a tag (v-prefixed first) or full SHA."""
    owner, name, _ = parse_issue_url(f'https://github.com/{repo}/issues/1')
    base = f'https://api.github.com/repos/{owner}/{name}'
    if version is not None and (not isinstance(version, str) or not version or not (SHA.fullmatch(version) or TAG.fullmatch(version))):
        raise ValueError('Version must be a simple tag or full lowercase commit SHA')
    choices = ([version] if version and SHA.fullmatch(version) else
               ([version, version[1:]] if version.startswith('v') else ['v' + version, version]) if version else ['HEAD'])
    for ref in choices:
        if ref == 'HEAD' or SHA.fullmatch(ref):
            response = client.get(f'{base}/commits/{ref}', timeout=20, follow_redirects=False)
            try:
                response.raise_for_status()
                sha = response.json()['sha']
                if not SHA.fullmatch(sha):
                    raise ValueError('Invalid commit SHA')
                return sha, ref
            except Exception as exc:
                raise BuildError(f'Unable to resolve GitHub ref {ref!r} (HTTP {response.status_code})') from exc
        response = client.get(f'{base}/git/ref/tags/{ref}', timeout=20, follow_redirects=False)
        if response.status_code == 404:
            continue
        try:
            response.raise_for_status()
            obj = response.json()['object']
            # Annotated tags point to tag objects; peel them until a commit.
            for _ in range(10):
                sha, kind = obj['sha'], obj['type']
                if not SHA.fullmatch(sha):
                    raise ValueError('Invalid object SHA')
                if kind == 'commit':
                    return sha, ref
                if kind != 'tag':
                    raise ValueError('Tag does not point to a commit')
                response = client.get(f'{base}/git/tags/{sha}', timeout=20, follow_redirects=False)
                response.raise_for_status()
                obj = response.json()['object']
            raise ValueError('Too many nested tags')
        except Exception as exc:
            raise BuildError(f'Unable to resolve GitHub tag {ref!r} (HTTP {response.status_code})') from exc
    raise BuildError('Neither requested tag exists')


def _write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    filename = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
            filename = f.name
            json.dump(data, f, indent=2)
            f.write('\n')
        os.replace(filename, path)
        filename = None
    finally:
        if filename:
            os.unlink(filename)


# This script runs in a non-root container, with no host mounts or host keys.
# pip builds execute project-controlled code; setup is networked and isolated.
SETUP = r'''set -eu
mkdir -p /var/tmp/repro
export GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
git -c init.templateDir= -c core.hooksPath=/dev/null init /var/tmp/repro/source
git -C /var/tmp/repro/source -c protocol.file.allow=never fetch --depth=1 --no-tags "$1" "$2"
git -C /var/tmp/repro/source -c core.hooksPath=/dev/null checkout --detach FETCH_HEAD
test "$(git -C /var/tmp/repro/source rev-parse HEAD)" = "$2"
python -m venv /var/tmp/repro/venv
shift 2
/var/tmp/repro/venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir /var/tmp/repro/source pytest "$@"
/var/tmp/repro/venv/bin/python -m pip freeze > /var/tmp/repro/packages.txt
''' 


class EnvironmentBuilder:
    def __init__(self, docker_client, http_client, *, base_image='python:3.11'):
        self.docker = docker_client
        self.http = http_client
        self.base_image = base_image

    def build(self, repo: str, version: str | None, output_dir: str | Path, *, timeout: int = 600, test_dependencies: list[str] | None = None) -> dict:
        started = time.monotonic()
        if not 0 < timeout <= 900:
            raise ValueError('Build timeout must be between 0 and 900 seconds')
        test_dependencies = list(test_dependencies or [])
        if any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.\-]*(?:\[[A-Za-z0-9_,.-]+\])?(?:[<>=!~]+[A-Za-z0-9.*_-]+)?', dep) for dep in test_dependencies):
            raise ValueError('Test dependencies must be simple package requirements')
        sha, selected = resolve_commit(repo, version, self.http)
        base = self.docker.images.get(self.base_image)
        digest = hashlib.sha256(json.dumps([repo.lower(), sha, base.id, 'builder-v3-var-tmp', test_dependencies]).encode()).hexdigest()[:32]
        image_tag = f'issue-repro-env:{digest}'
        cache_hit = True
        try:
            image = self.docker.images.get(image_tag)
        except Exception as exc:
            import docker.errors
            if not isinstance(exc, docker.errors.ImageNotFound):
                raise
            cache_hit = False
            owner, name, _ = parse_issue_url(f'https://github.com/{repo}/issues/1')
            url = f'https://github.com/{owner}/{name}.git'
            container = self.docker.containers.create(
                base.id, command=['sh', '-c', SETUP, 'setup', url, sha, *test_dependencies], user='65534:65534',
                network_mode='bridge', mem_limit='1g', nano_cpus=1_000_000_000,
                pids_limit=256, cap_drop=['ALL'], security_opt=['no-new-privileges:true'],
                environment={'HOME': '/tmp', 'PIP_NO_INPUT': '1'}, use_config_proxy=False, init=True,
                working_dir='/tmp')
            try:
                container.start()
                try:
                    status = container.wait(timeout=timeout)['StatusCode']
                except Exception as exc:
                    if not _is_wait_timeout(exc): raise
                    container.kill()
                    raise BuildError('Environment build timed out') from exc
                if status != 0:
                    log = container.logs(stdout=True, stderr=True, tail=100).decode('utf-8', 'replace')[-8000:]
                    raise BuildError(f'Environment build failed (exit {status}):\n{log}')
                image = container.commit(repository='issue-repro-env', tag=digest)
            finally:
                container.remove(force=True)
        # Inspect through the same network-disabled, non-root runtime used for tests.
        with Sandbox(image=image_tag, client=self.docker, max_timeout=60,
                     working_dir='/var/tmp/repro/source') as sandbox:
            result = sandbox.run(['/var/tmp/repro/venv/bin/python', '-c',
                "import json,platform; print(json.dumps({'python':platform.python_version(),'packages':open('/var/tmp/repro/packages.txt').read().splitlines()}))"])
        if result.timed_out or result.exit_code != 0:
            raise BuildError('Unable to inspect built environment: ' + result.output[-2000:])
        details = json.loads(result.output)
        metadata = {'repo': repo, 'requested_version': version, 'selected_ref': selected,
                    'used_default_branch': version is None, 'commit': sha, 'base_image_id': base.id,
                    'image': image_tag, 'image_id': image.id, 'cache_hit': cache_hit, 'test_dependencies': test_dependencies, **details}
        # Baseline runs in the same offline, non-root environment as later tests.
        try:
            remaining = min(300, timeout - (time.monotonic() - started))
            if remaining <= 0:
                metadata['baseline'] = {'status': 'timeout', 'counts': None, 'failures': []}
            else:
                with Sandbox(image=image_tag, client=self.docker, max_timeout=remaining,
                         working_dir='/var/tmp/repro/source') as sandbox:
                    result = sandbox.run(['/var/tmp/repro/venv/bin/python', '-m', 'pytest',
                                          '-ra', '-p', 'no:cacheprovider'], timeout=remaining)
                metadata['baseline'] = baseline_from_result(result)
        except Exception:  # noqa: BLE001 - record an inconclusive baseline without leaking output.
            metadata['baseline'] = {'status': 'runner_error', 'counts': None, 'failures': []}
        _write_json(Path(output_dir) / 'environment.json', metadata)
        return metadata


def main():
    parser = argparse.ArgumentParser(description='Build an environment for a public GitHub Python repo')
    parser.add_argument('repo', help='owner/repository')
    parser.add_argument('--version', default=None)
    parser.add_argument('--output-dir', default='environment')
    parser.add_argument('--run-tests', action='store_true', help='Run pytest with networking disabled')
    parser.add_argument('--test-dependency', action='append', default=[], help='Additional test package requirement; repeat as needed')
    args = parser.parse_args()
    import docker
    import httpx
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
    if os.getenv('GITHUB_TOKEN'):
        headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
    try:
        with closing(docker.from_env()) as dc, httpx.Client(headers=headers, timeout=20) as hc:
            meta = EnvironmentBuilder(dc, hc).build(args.repo, args.version, args.output_dir, test_dependencies=args.test_dependency)
            if args.run_tests:
                with Sandbox(image=meta['image'], client=dc, max_timeout=300,
                             working_dir='/var/tmp/repro/source') as sandbox:
                    result = sandbox.run(['/var/tmp/repro/venv/bin/python', '-m', 'pytest', '-ra', '-p', 'no:cacheprovider'], timeout=300)
                print(result.output)
                if result.timed_out or result.exit_code != 0:
                    parser.exit(1, f'Offline pytest failed: exit={result.exit_code}, timeout={result.timed_out}\n')
        print(f"Built {meta['image']} at {meta['commit']} (cache hit: {meta['cache_hit']})")
        print(f"Saved {Path(args.output_dir) / 'environment.json'}")
    except (BuildError, ValueError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')

if __name__ == '__main__': main()

