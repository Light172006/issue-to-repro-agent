"""Compare Spark-only and escalation runs. Paid calls require explicit opt-in."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _load_env(path: Path = Path('.env')) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        k, v = line.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip().strip('\'\"'))


def _run_arm(url: str, arm: str, force_escalate_at_step: int | None = None) -> tuple[dict | None, Path | None, int]:
    command = [sys.executable, '-m', 'repro.cli', url]
    if arm.startswith('spark'):
        command.append('--no-escalation')
    elif force_escalate_at_step:
        command.extend(['--force-escalate-at-step', str(force_escalate_at_step)])
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    folders = [line.removeprefix('Run folder: ').strip() for line in completed.stdout.splitlines()
               if line.startswith('Run folder: ')]
    if not folders:
        return None, None, completed.returncode
    try:
        folder = Path(folders[-1])
        data = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
        return data, folder, completed.returncode
    except (OSError, ValueError):
        return None, None, completed.returncode


def _print_row(url: str, arm: str, data: dict | None, folder: Path | None, returncode: int):
    if data is None:
        print(f'{url} | {arm} | error (exit {returncode})', flush=True)
        return
    esc = data.get('escalation') or {}
    print(f"{url} | {arm} | {data.get('status')} | {data.get('steps')} | {data.get('duration')} | "
          f"{esc.get('escalated', False)} | {esc.get('spark_cost', 'unknown')} | "
          f"{esc.get('wonder_cost', '0')} | {data.get('cost_usd')} | {folder}", flush=True)


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('issues', type=Path, help='One issue URL per line')
    parser.add_argument('--approve-paid', action='store_true')
    parser.add_argument('--force-escalate-at-step', type=int, default=None)
    args = parser.parse_args()
    urls = [line.strip() for line in args.issues.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]
    print('Each issue uses up to three runs; each run has a $1 cap, so worst case is $3 per issue.')
    print('Example trace: 18,944 input and 968 output tokens; at Wonder rates that is $0.095136 for those seven calls.')
    print('Actual token counts vary; parsing and the other arm costs are additional.')
    if args.force_escalate_at_step:
        print('PLUMBING TEST: forced escalation is not evidence of an escalation benefit.')
    if not args.approve_paid:
        print('No calls made. Use --approve-paid only after approving the estimate.')
        return 0
    print('issue | arm | outcome | steps | seconds | escalated | spark USD | wonder USD | total USD | folder')
    failed = False
    for url in urls:
        if args.force_escalate_at_step:
            data, folder, code = _run_arm(url, 'forced-escalation', args.force_escalate_at_step)
            _print_row(url, 'forced-escalation', data, folder, code)
            if data is None or data.get('status') != 'reproduced':
                failed = True
            continue

        # Sequence: run Spark-only twice; run escalation only if both Spark runs fail to reproduce.
        spark_success = False
        for arm in ('spark-1', 'spark-2'):
            data, folder, code = _run_arm(url, arm)
            _print_row(url, arm, data, folder, code)
            if data is not None and data.get('status') == 'reproduced':
                spark_success = True

        if spark_success:
            print(f'{url} | escalation | skipped (spark succeeded) | - | - | False | - | 0 | 0 | -', flush=True)
        else:
            data, folder, code = _run_arm(url, 'escalation')
            _print_row(url, 'escalation', data, folder, code)
            if data is None or data.get('status') != 'reproduced':
                failed = True

    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
