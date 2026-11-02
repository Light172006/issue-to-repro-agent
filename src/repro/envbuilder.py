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
from repro.testdeps import discover_test_dependencies

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
    """Atomically write JSON to path via a sibling temp file.

    On Windows, os.replace raises PermissionError (WinError 5) when the
    destination is concurrently locked.  Production writes are always
    sequential; the retry guards the concurrent stress test and any
    future caller.
    """
    import sys as _sys
    path.parent.mkdir(parents=True, exist_ok=True)
    filename = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
            filename = f.name
            json.dump(data, f, indent=2)
            f.write('\n')
        max_attempts = 100 if _sys.platform == 'win32' else 1
        for _attempt in range(max_attempts):
            try:
                os.replace(filename, path)
                filename = None
                break
            except PermissionError:
                if _attempt == max_attempts - 1 or _sys.platform != 'win32':
                    raise
                import random as _random
                import time as _time
                _time.sleep(0.005 + _random.uniform(0.002, 0.015))
    finally:
        if filename:
            try:
                os.unlink(filename)
            except OSError:
                pass


# This script runs in a non-root container, with no host mounts or host keys.
# pip builds execute project-controlled code; setup is networked and isolated.
SETUP = r'''set -eu
mkdir -p /var/tmp/repro
export GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
git -c init.templateDir= -c core.hooksPath=/dev/null init /var/tmp/repro/source
git -C /var/tmp/repro/source -c protocol.file.allow=never fetch --depth=1 --no-tags "$1" "$2"
git -C /var/tmp/repro/source -c core.hooksPath=/dev/null checkout --detach FETCH_HEAD
test "$(git -C /var/tmp/repro/source rev-parse HEAD)" = "$2"
installer="$3"
shift 3
python -c "$installer" "$@"
''' 


def _fetch_config_files(repo: str, sha: str, client) -> dict[str, str]:
    """Fetch key project config files from GitHub at the given commit SHA.

    Returns a {filename: text} dict.  Any file that cannot be fetched is
    silently omitted; this is a best-effort discovery step, not a hard
    requirement.  Each file is capped at 128 KiB to bound memory use.
    """
    import base64 as _b64
    owner, name, _ = parse_issue_url(f'https://github.com/{repo}/issues/1')
    base_url = f'https://api.github.com/repos/{owner}/{name}/contents/'
    targets = [
        'pyproject.toml', 'setup.cfg', 'setup.py', 'tox.ini',
        'pytest.ini', 'noxfile.py',
        'requirements-dev.txt', 'requirements-test.txt',
        'requirements_dev.txt', 'requirements_test.txt',
        'requirements/dev.txt', 'requirements/test.txt',
    ]
    files: dict[str, str] = {}
    for target in targets:
        try:
            resp = client.get(base_url + target, params={'ref': sha},
                              timeout=10, follow_redirects=False)
            if resp.status_code != 200:
                continue
            data = resp.json()
            if data.get('type') != 'file' or data.get('encoding') != 'base64':
                continue
            raw = _b64.b64decode(data['content'])
            if len(raw) > 131072:
                continue  # skip files > 128 KiB
            files[target] = raw.decode('utf-8', 'replace')
        except Exception:  # noqa: BLE001,S112 - non-fatal; caller records warnings.
            continue
    return files


def _discover_deps(repo: str, sha: str, client) -> tuple[list[str], list[str]]:
    """Fetch config files and derive plain test-package requirements via testdeps.

    Returns (extra_packages, warnings).  Only plain package requirements and
    pytest plugins are returned; extras like .[test] require the caller to
    extend the source install argument, which is not yet supported.
    On any exception returns empty lists and a single warning entry.
    """
    try:
        files = _fetch_config_files(repo, sha, client)
        plan = discover_test_dependencies(files)
        packages = list(plan.requirements) + [p for p in plan.plugins if p not in plan.requirements]
        warnings = list(plan.warnings)
        if plan.extras:
            warnings.append(f'discovered extras {list(plan.extras)!r} not yet wired into install command')
        return packages, warnings
    except Exception as exc:  # noqa: BLE001 - never block a build on discovery.
        return [], [f'discovery error: {type(exc).__name__}: {exc}']


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
        # Discover plain test package requirements from project config files.
        # Failures are recorded in environment.json and never block the build.
        _disc_packages, _disc_warnings = _discover_deps(repo, sha, self.http)
        for pkg in _disc_packages:
            if pkg not in test_dependencies:
                test_dependencies.append(pkg)
        base = self.docker.images.get(self.base_image)
        testdeps_code = Path(__file__).with_name('testdeps.py').read_text(encoding='utf-8')
        installenv_code = Path(__file__).with_name('installenv.py').read_text(encoding='utf-8')
        testdeps_body = re.sub(r'^from __future__ import annotations\s*\n?', '', testdeps_code, flags=re.MULTILINE)
        installenv_body = re.sub(r'^from __future__ import annotations\s*\n?', '', installenv_code, flags=re.MULTILINE)
        installer = 'from __future__ import annotations\n' + testdeps_body + '\n' + installenv_body
        installer_digest = hashlib.sha256(installer.encode()).hexdigest()
        digest = hashlib.sha256(json.dumps([repo.lower(), sha, base.id, 'builder-v4-date-resolution',
                                             installer_digest, test_dependencies]).encode()).hexdigest()[:32]
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
                base.id, command=['sh', '-c', SETUP, 'setup', url, sha, installer,
                                  *test_dependencies], user='65534:65534',
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
                "import json,pathlib,platform; root=pathlib.Path('/var/tmp/repro'); disc=json.loads((root/'discovery.json').read_text()) if (root/'discovery.json').exists() else {}; print(json.dumps({'python':platform.python_version(),'packages':(root/'packages.txt').read_text().splitlines(),'resolution':json.loads((root/'resolution.json').read_text()),'discovery':disc}))"])
        if result.timed_out or result.exit_code != 0:
            raise BuildError('Unable to inspect built environment: ' + result.output[-2000:])
        details = json.loads(result.output)
        metadata = {'repo': repo, 'requested_version': version, 'selected_ref': selected,
                    'used_default_branch': version is None, 'commit': sha, 'base_image_id': base.id,
                    'image': image_tag, 'image_id': image.id, 'cache_hit': cache_hit,
                    'test_dependencies': test_dependencies,
                    'test_dependency_discovery': details.get('discovery') or {
                        'discovered_packages': _disc_packages,
                        'warnings': _disc_warnings,
                    }, **details}
        metadata['resolved_packages'] = list(details['packages'])
        metadata['resolution'] = details.get('resolution', {'strategy': 'unknown', 'reason_for_fallback': None,
                                                            'cutoff': None, 'install_duration_s': None})
        # Baseline runs in the same offline, non-root environment as later tests.
        try:
            remaining = min(300, timeout - (time.monotonic() - started))
            if remaining <= 0:
                metadata['baseline'] = {'status': 'timeout', 'counts': None, 'failures': []}
            else:
                with Sandbox(image=image_tag, client=self.docker, max_timeout=remaining,
                         working_dir='/var/tmp/repro/source') as sandbox:
                    result = sandbox.run(['/var/tmp/repro/venv/bin/python', '-m', 'pytest',
                                          '-ra', '-p', 'no:cacheprovider', '-p', 'no:cov', '-o', 'addopts=', '--color=no'], timeout=remaining)
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
                    result = sandbox.run(['/var/tmp/repro/venv/bin/python', '-m', 'pytest', '-ra', '-p', 'no:cacheprovider', '-p', 'no:cov', '-o', 'addopts=', '--color=no'], timeout=300)
                print(result.output)
                if result.timed_out or result.exit_code != 0:
                    parser.exit(1, f'Offline pytest failed: exit={result.exit_code}, timeout={result.timed_out}\n')
        print(f"Built {meta['image']} at {meta['commit']} (cache hit: {meta['cache_hit']})")
        print(f"Saved {Path(args.output_dir) / 'environment.json'}")
    except (BuildError, ValueError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')

if __name__ == '__main__': main()

