"""Check Step 12 environments with production builder defaults; no model calls."""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import uuid
from contextlib import closing
from pathlib import Path

import docker
import httpx

from repro.envbuilder import BuildError, EnvironmentBuilder
from repro.sandbox import Sandbox
from repro.trace import redact

_COUNT = re.compile(r'\b(\d+)\s+(passed|failed|skipped|error|errors)\b')
_FAILURE = re.compile(r'^(?:FAILED|ERROR)\s+([^\s]+)', re.MULTILINE)
_SUMMARY = re.compile(r'^=+\s+.*\b(?:passed|failed|skipped|error|errors)\b.*=+\s*$', re.MULTILINE)


def parse_pytest(output: str, *, truncated: bool = False) -> dict:
    """Parse the final summary and names; never infer zero from missing evidence."""
    clean = re.sub(r'\x1b\[[0-9;]*m', '', output)
    summaries = list(_SUMMARY.finditer(clean))
    counts = None
    if summaries:
        counts = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0}
        for number, label in _COUNT.findall(summaries[-1].group()):
            counts['errors' if label in ('error', 'errors') else label] += int(number)
    # Collection failures may be reported as ERROR rather than FAILED.
    names = sorted(set(_FAILURE.findall(clean)))
    return {'counts': counts, 'failure_names': names, 'truncated': truncated}


def baseline_recorded(metadata: dict, expected_names: list[str]) -> str:
    """Check explicit baseline fields only; issue-list expectations are not metadata."""
    if not expected_names:
        return 'not applicable'
    baseline = metadata.get('baseline')
    recorded = [metadata.get('baseline_failures'), metadata.get('pre_existing_failures')]
    if isinstance(baseline, dict):
        recorded.extend([baseline.get('failures'), baseline.get('failed_tests'),
                         baseline.get('pre_existing_failures')])
    values: set[str] = set()
    for value in recorded:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    values.add(item)
                elif isinstance(item, dict) and isinstance(item.get('test'), str):
                    values.add(item['test'])
    return 'yes' if all(name in values for name in expected_names) else 'NOT RECORDED'


def compare_suite(parsed: dict, expected: dict) -> str:
    counts = parsed['counts']
    if counts is None or parsed['truncated']:
        return 'unknown'
    if counts['errors']:
        return 'no (collection errors)'
    same = all(counts[key] == expected.get(key) for key in ('passed', 'failed', 'skipped'))
    expected_names = {item['test'] for item in expected.get('failures', []) if isinstance(item, dict) and 'test' in item}
    if same and expected_names and not expected_names.issubset(set(parsed['failure_names'])):
        return 'no (failure names differ)'
    return 'yes' if same else 'no'


def classify_build_error(error: Exception) -> str:
    message = str(error).lower()
    if isinstance(error, BuildError):
        if 'timed out' in message:
            return 'build timeout'
        if 'resolve' in message or 'tag exists' in message:
            return 'ref resolution failed'
        if any(term in message for term in ('no matching distribution', 'could not find a version',
                                             'resolutionimpossible', 'conflicting dependencies')):
            return 'dependency resolution failed'
        if 'environment build failed' in message:
            return 'install or checkout failed'
        return 'environment build failed'
    if isinstance(error, docker.errors.ImageNotFound):
        return 'base image missing'
    if isinstance(error, docker.errors.DockerException):
        return 'docker unavailable or denied'
    if isinstance(error, ValueError):
        return 'invalid issue metadata'
    return f'error ({type(error).__name__})'


def run_case(case: dict, builder, client, output_dir: Path, *, test_timeout: int = 300) -> dict:
    """Build with the CLI defaults; run the same offline pytest command."""
    started = time.monotonic()
    record = {'url': case.get('url'), 'build_status': None, 'build_seconds': None,
              'test_status': 'not run', 'counts': None, 'failure_names': [],
              'counts_match': 'unknown', 'baseline_recorded': 'unknown',
              'notes': [], 'environment_file': None}
    expected = case.get('suite_older', {})
    expected_names = [item['test'] for item in expected.get('failures', [])
                      if isinstance(item, dict) and isinstance(item.get('test'), str)]
    try:
        # Deliberately omit test_dependencies: exactly the production default.
        metadata = builder.build(case['library'], case['older_ref'], output_dir)
        record['build_seconds'] = round(time.monotonic() - started, 2)
        record['build_status'] = 'ok'
        record['environment_file'] = str(output_dir / 'environment.json')
        if metadata.get('commit') != case['older_ref']:
            record['test_status'] = 'commit mismatch'
            return record
        try:
            saved = json.loads((output_dir / 'environment.json').read_text(encoding='utf-8'))
            record['baseline_recorded'] = baseline_recorded(saved, expected_names)
        except (OSError, ValueError, TypeError):
            record['baseline_recorded'] = 'unreadable metadata'
        with Sandbox(image=metadata['image'], client=client, max_timeout=test_timeout,
                     working_dir='/var/tmp/repro/source') as sandbox:
            result = sandbox.run(['/var/tmp/repro/venv/bin/python', '-m', 'pytest', '-ra',
                                  '-p', 'no:cacheprovider'], timeout=test_timeout)
        output = redact(result.output, secrets=tuple(os.environ.get(k, '')
                        for k in ('META_MODEL_API_KEY', 'GITHUB_TOKEN')))
        output_dir.joinpath('pytest-output.txt').write_text(output, encoding='utf-8')
        truncated = result.original_length is not None and result.original_length > 32000
        parsed = parse_pytest(output, truncated=truncated)
        record['counts'] = parsed['counts']
        record['failure_names'] = parsed['failure_names']
        record['counts_match'] = compare_suite(parsed, expected)
        if result.timed_out:
            record['test_status'] = 'timeout'
        elif result.exit_code == 2 or (parsed['counts'] and parsed['counts']['errors']):
            record['test_status'] = 'collection error'
        elif result.exit_code == 5:
            record['test_status'] = 'no tests collected'
        elif result.exit_code in (0, 1):
            record['test_status'] = 'completed' if parsed['counts'] is not None else 'unparsed output'
        else:
            record['test_status'] = f'pytest error (exit {result.exit_code})'
        if 'ModuleNotFoundError' in output or 'No module named' in output:
            record['notes'].append('Missing dependency in production environment; no pins were added.')
        if parsed['truncated']:
            record['notes'].append('Output truncated; counts or failure names may be incomplete.')
        hand_install = str(case.get('install_command', ''))
        if any(marker in hand_install for marker in ('.[tests]', '.[dev]', 'pytest==', 'mypy==', 'pytest-cov')):
            record['notes'].append('Hand check used extras or pins; this production build did not. '
                                   'Differences may make the case environment-limited.')
    except Exception as exc:  # noqa: BLE001 - continue checking independent issues.
        if record['build_status'] is None:
            record['build_status'] = classify_build_error(exc)
            record['build_seconds'] = round(time.monotonic() - started, 2)
        else:
            record['test_status'] = f'error ({type(exc).__name__})'
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--issues', type=Path, default=Path('bench/step12_issues.json'))
    parser.add_argument('--output-dir', type=Path, default=Path('environment/step12-check'))
    args = parser.parse_args()
    try:
        cases = json.loads(args.issues.read_text(encoding='utf-8'))
        if not isinstance(cases, list) or not cases:
            raise ValueError('Issue list must be a nonempty JSON list')
        headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'issue-to-repro-agent'}
        if os.environ.get('GITHUB_TOKEN'):
            headers['Authorization'] = 'Bearer ' + os.environ['GITHUB_TOKEN']
        run_dir = args.output_dir / uuid.uuid4().hex
        run_dir.mkdir(parents=True)
        with closing(docker.from_env()) as client, httpx.Client(headers=headers, timeout=20) as http:
            builder = EnvironmentBuilder(client, http)
            rows = []
            print('Issue | Build | Build s | Tests | Passed/failed/skipped/errors | Counts match | Baseline recorded', flush=True)
            for index, case in enumerate(cases, 1):
                row = run_case(case, builder, client, run_dir / f'case-{index}')
                rows.append(row)
                counts = row['counts']
                display = '/'.join(str(counts[k]) for k in ('passed', 'failed', 'skipped', 'errors')) if counts else 'unknown'
                print(f"{row['url']} | {row['build_status']} | {row['build_seconds']} | {row['test_status']} | "
                      f"{display} | {row['counts_match']} | {row['baseline_recorded']}", flush=True)
                print('  Failing tests: ' + (', '.join(row['failure_names']) or 'none reported'), flush=True)
                for note in row['notes']:
                    print('  Note: ' + note, flush=True)
                if row['environment_file']:
                    print('  Metadata: ' + row['environment_file'], flush=True)
            (run_dir / 'summary.json').write_text(json.dumps(rows, indent=2) + '\n', encoding='utf-8')
        print(f'Full results: {run_dir}')
        print('If hand verification needs pins absent from the production builder, drop the issue or classify it as environment-limited.')
        return int(any(row['build_status'] != 'ok' or row['test_status'] != 'completed' or
                       row['counts_match'] != 'yes' or row['baseline_recorded'] not in ('yes', 'not applicable') for row in rows))
    except (OSError, ValueError, docker.errors.DockerException) as exc:
        print(f'Cannot run environment checks: {type(exc).__name__}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
