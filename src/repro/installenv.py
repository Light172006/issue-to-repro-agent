"""Trusted setup code executed inside the network-enabled build container."""
from __future__ import annotations

import datetime
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path


def run_command(command: list[str], timeout: float) -> tuple[int, str]:
    """Keep only the last 32 KiB of combined installer output in memory."""
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    tail = bytearray()
    truncated = False

    def consume() -> None:
        nonlocal truncated
        assert proc.stdout is not None
        while chunk := proc.stdout.read(8192):
            tail.extend(chunk)
            if len(tail) > 32768:
                truncated = True
                del tail[:-32768]

    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    try:
        code = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise
    finally:
        reader.join(timeout=2)
        if proc.stdout is not None:
            proc.stdout.close()
    return code, ('[output truncated]\n' if truncated else '') + tail.decode('utf-8', 'replace')


def resolve_install(source: Path, root: Path, extra: list[str], *, run=run_command,
                    clock=time.monotonic, timeout: float = 540) -> dict:
    """Install at the commit cutoff; retry latest only for resolution failure."""
    started = clock()

    def invoke(command: list[str]) -> tuple[int, str]:
        remaining = timeout - (clock() - started)
        if remaining <= 0:
            raise TimeoutError('install timeout')
        try:
            return run(command, remaining)
        except subprocess.TimeoutExpired:
            raise TimeoutError('install timeout') from None

    code, date = invoke(['git', '-C', str(source), 'show', '-s', '--format=%cI', 'HEAD'])
    cutoff = date.strip()
    try:
        parsed = datetime.datetime.fromisoformat(cutoff)
        if parsed.utcoffset() is None:
            raise ValueError('commit timestamp has no timezone')
    except ValueError:
        raise RuntimeError('invalid commit timestamp') from None
    if code:
        raise RuntimeError('cannot read commit timestamp')

    bootstrap = root / 'resolver'
    code, _ = invoke([sys.executable, '-m', 'venv', str(bootstrap)])
    if code:
        raise RuntimeError('resolver bootstrap failed')
    bootstrap_python = str(bootstrap / 'bin' / 'python')
    code, _ = invoke([bootstrap_python, '-m', 'pip', 'install', '--disable-pip-version-check', 'uv'])
    if code:
        raise RuntimeError('resolver bootstrap failed')
    uv = str(bootstrap / 'bin' / 'uv')
    venv = root / 'venv'
    previous_reason = None
    for strategy in ('date_bounded', 'unbounded_latest'):
        if venv.exists():
            shutil.rmtree(venv)
        code, _ = invoke([sys.executable, '-m', 'venv', str(venv)])
        if code:
            raise RuntimeError('virtualenv creation failed')
        command = [uv, 'pip', 'install', '--python', str(venv / 'bin' / 'python')]
        if strategy == 'date_bounded':
            command += ['--exclude-newer', cutoff]
        command += [str(source), 'pytest', *extra]
        code, output = invoke(command)
        if code == 0:
            return {'strategy': strategy, 'reason_for_fallback': previous_reason,
                    'cutoff': cutoff, 'install_duration_s': round(clock() - started, 3)}
        lower = output.lower()
        no_solution = any(token in lower for token in (
            'no solution found', 'no versions of', 'no matching distribution',
            'not compatible with the current python', 'requires a different python'))
        if strategy == 'date_bounded' and no_solution:
            previous_reason = 'date_bounded_resolution_failed'
            continue
        raise RuntimeError('dependency resolution failed' if no_solution else 'environment installation failed')
    raise RuntimeError('dependency resolution failed')


def main() -> None:
    root = Path('/var/tmp/repro')
    try:
        data = resolve_install(root / 'source', root, sys.argv[1:])
        (root / 'resolution.json').write_text(json.dumps(data), encoding='utf-8')
        code, output = run_command([str(root / 'resolver/bin/uv'), 'pip', 'freeze', '--python',
                                    str(root / 'venv/bin/python')], 30)
        if code or output.startswith('[output truncated]'):
            raise RuntimeError('unable to list installed packages')
        (root / 'packages.txt').write_text(output, encoding='utf-8')
    except (OSError, RuntimeError, TimeoutError) as exc:
        print(f'Build setup failed: {exc}', file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
