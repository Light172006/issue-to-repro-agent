"""Minimize and reverify a previously saved run; no model calls."""
from __future__ import annotations

import argparse
import json
from contextlib import closing
from pathlib import Path

import docker

from repro.llm import load_config
from repro.minimizer import minimize_run
from repro.parser import IssueRecord


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_folder', type=Path)
    args = parser.parse_args()
    folder = args.run_folder
    try:
        events = [json.loads(line) for line in (folder / 'parser_trace.jsonl').read_text(encoding='utf-8').splitlines()]
        records = [event for event in events if event.get('event') == 'parser_result' and event.get('fallback') is False]
        if not records:
            raise ValueError('No validated parsed issue')
        record = IssueRecord.model_validate(records[-1]['record'])
        env = json.loads((folder / 'environment.json').read_text(encoding='utf-8'))
        fixed_file = folder / 'fixed_environment' / 'environment.json'
        fixed = json.loads(fixed_file.read_text(encoding='utf-8')) if fixed_file.exists() else None
        previous = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
        prior_fixed = previous.get('checks', {}).get('fixed_version')
        if prior_fixed and (not fixed or not prior_fixed.get('commit') or
                            fixed.get('commit') != prior_fixed['commit'] or
                            fixed.get('repo', '').lower() != record.repo.lower()):
            raise ValueError('Fixed environment does not match prior verified commit')
        settings = load_config(Path('config/limits.yaml')).get('minimizer', {})
        with closing(docker.from_env()) as client:
            data = minimize_run(folder, record, client, env['image'],
                                fixed_image=fixed['image'] if fixed else None,
                                fixed_ref=fixed['selected_ref'] if fixed else None,
                                config=settings, enabled=settings.get('enabled', True))
        details = data['minimization']
        print(json.dumps(details, indent=2))
        checks = data['checks']
        conditions = {
            'five identical failures': checks.get('repeated_runs', {}).get('consistent') is True,
            'buggy fails and fixed passes': bool((checks.get('fixed_version') or {}).get('passed')),
            'minimized and same failure': details['status'] == 'minimized' and details['final_lines'] < details['original_lines'],
            'confidence computed': data.get('confidence') is not None,
        }
        print(f"Confidence: {data.get('confidence')}")
        for name, passed in conditions.items():
            print(f'{name}: {"PASS" if passed else "FAIL"}')
        return 0 if all(conditions.values()) else 1
    except Exception as exc:  # noqa: BLE001 - don't leak tokens.
        print(f'Step 10 failed: {type(exc).__name__}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
