"""Compare Spark-only and escalation runs. Paid calls require explicit opt-in."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('issues', type=Path, help='One issue URL per line')
    parser.add_argument('--approve-paid', action='store_true')
    parser.add_argument('--force-escalate-at-step', type=int, default=None)
    args = parser.parse_args()
    urls = [line.strip() for line in args.issues.read_text(encoding='utf-8').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]
    print('Each issue uses three runs; each run has a $1 cap, so worst case is $3 per issue.')
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
        for arm in ('spark-1', 'spark-2', 'escalation'):
            command = [sys.executable, '-m', 'repro.cli', url]
            if arm.startswith('spark'):
                command.append('--no-escalation')
            elif args.force_escalate_at_step:
                command.extend(['--force-escalate-at-step', str(args.force_escalate_at_step)])
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            folders = [line.removeprefix('Run folder: ').strip() for line in completed.stdout.splitlines()
                       if line.startswith('Run folder: ')]
            try:
                folder = Path(folders[-1])
                data = json.loads((folder / 'result.json').read_text(encoding='utf-8'))
                esc = data.get('escalation') or {}
                print(f"{url} | {arm} | {data.get('status')} | {data.get('steps')} | {data.get('duration')} | "
                      f"{esc.get('escalated', False)} | {esc.get('spark_cost', 'unknown')} | "
                      f"{esc.get('wonder_cost', '0')} | {data.get('cost_usd')} | {folder}", flush=True)
            except (IndexError, OSError, ValueError):
                failed = True
                print(f'{url} | {arm} | error (exit {completed.returncode})', flush=True)
    return int(failed)


if __name__ == '__main__':
    raise SystemExit(main())
