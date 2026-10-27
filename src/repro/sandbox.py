"""Run one command per isolated, disposable Docker container."""
from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    output: str
    timed_out: bool
    original_length: int | None = None


def _is_wait_timeout(error: Exception) -> bool:
    """Recognize direct and wrapped HTTP read timeouts, not other errors."""
    from requests.exceptions import ConnectionError, Timeout
    from urllib3.exceptions import ReadTimeoutError
    if isinstance(error, Timeout):
        return True
    if not isinstance(error, ConnectionError):
        return False
    pending = [error]
    visited = set()
    while pending:
        item = pending.pop()
        if not isinstance(item, BaseException) or id(item) in visited:
            continue
        visited.add(id(item))
        if isinstance(item, (Timeout, ReadTimeoutError)):
            return True
        pending.extend(item.args)
        pending.extend((item.__cause__, item.__context__))
    return False


def _read_log(container):
    stream = container.logs(stdout=True, stderr=True, stream=True)
    if isinstance(stream, bytes):
        stream = (stream,)
    first = bytearray()
    last = bytearray()
    total = 0
    try:
        for chunk in stream:
            total += len(chunk)
            if len(first) < 16000:
                first.extend(chunk[:16000 - len(first)])
            last.extend(chunk[-16000:])
            if len(last) > 16000:
                del last[:-16000]
    finally:
        if hasattr(stream, 'close'):
            stream.close()
    if total <= 16000:
        data = first
    elif total <= 32000:
        data = first + last[-(total - len(first)):]
    else:
        note = f'\n... output truncated: {total - len(first) - len(last)} bytes removed from {total} ...\n'
        data = first + note.encode('ascii') + last
    return data.decode('utf-8', errors='replace'), total


class Sandbox:
    """Local Docker sandbox. Uses Linux containers and never mounts host files.

    Each invocation creates a fresh container. Changes do not persist to the next
    invocation; image construction and run output mounts are later-step work.
    """
    def __init__(self, image: str = 'python:3.11-slim', *, client=None,
                 memory: str = '512m', nano_cpus: int = 1_000_000_000,
                 pids_limit: int = 128, max_timeout: float = 60, working_dir: str = '/tmp',
                 writable_mount: str | Path | None = None):
        if nano_cpus <= 0 or pids_limit <= 0 or max_timeout <= 0:
            raise ValueError('CPU, process and timeout limits must be positive')
        if client is None:
            import docker
            client = docker.from_env()
            self._owns_client = True
        else:
            self._owns_client = False
        self._closed = False
        self.client = client
        self.image = image
        self.memory = memory
        self.nano_cpus = nano_cpus
        self.pids_limit = pids_limit
        self.max_timeout = max_timeout
        if not working_dir.startswith('/') or '..' in working_dir.split('/'):
            raise ValueError('working_dir must be an absolute container path')
        self.working_dir = working_dir
        self.writable_mount = None
        if writable_mount is not None:
            path = Path(writable_mount)
            if path.is_symlink():
                raise ValueError('writable_mount must not be a symlink')
            if path.name != 'repro' or path.parent.parent.name != 'runs':
                raise ValueError('writable_mount must be runs/<id>/repro')
            path.mkdir(parents=True, exist_ok=True)
            if path.resolve().name != 'repro' or path.resolve().parent.parent.name != 'runs':
                raise ValueError('writable_mount resolves outside runs/<id>/repro')
            if not path.is_dir():
                raise ValueError('writable_mount must be a directory')
            # UID 65534 must be able to write on Linux; Docker Desktop translates
            # bind mount permissions on Windows and macOS.
            if os.name != 'nt':
                path.chmod(0o777)
            self.writable_mount = str(path.resolve())

    def close(self):
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def run(self, command: Sequence[str], *, timeout: float = 30) -> SandboxResult:
        """Run a command without external network access, including pytest."""
        return self._run(command, timeout=timeout, network_mode='none')

    def run_setup(self, command: Sequence[str], *, timeout: float = 30) -> SandboxResult:
        """Run trusted setup commands with networking; never run issue code here."""
        return self._run(command, timeout=timeout, network_mode='bridge')

    def _run(self, command: Sequence[str], *, timeout: float, network_mode: str) -> SandboxResult:
        if self._closed:
            raise RuntimeError('Sandbox is closed')
        if (not isinstance(command, (list, tuple)) or not command or
                any(not isinstance(arg, str) or not arg for arg in command)):
            raise ValueError('command must be a non-empty list of non-empty strings')
        if timeout <= 0 or timeout > self.max_timeout:
            raise ValueError('timeout must be positive and within the sandbox maximum')
        mount_options = {}
        if self.writable_mount is not None:
            mount_options['volumes'] = {
                self.writable_mount: {'bind': '/work/repro', 'mode': 'rw'}
            }
        if self.writable_mount is not None or self.working_dir.startswith('/var/tmp/repro'):
            scratch = {'/tmp': 'rw,noexec,nosuid,size=64m'}
            home = '/tmp'
        else:
            scratch = {'/var/tmp': 'rw,noexec,nosuid,size=64m'}
            home = '/var/tmp'
        environment = {'HOME': home, 'TMPDIR': home, 'PYTHONDONTWRITEBYTECODE': '1'}
        if self.writable_mount is not None:
            environment['PATH'] = '/var/tmp/repro/venv/bin:/usr/local/bin:/usr/bin:/bin'
        container = self.client.containers.create(
            self.image, command=list(command), user='65534:65534',
            network_mode=network_mode, mem_limit=self.memory,
            nano_cpus=self.nano_cpus, pids_limit=self.pids_limit,
            cap_drop=['ALL'], security_opt=['no-new-privileges:true'],
            read_only=True, tmpfs=scratch,
            working_dir=self.working_dir, environment=environment,
            use_config_proxy=False, init=True, **mount_options,
        )
        timed_out = False
        exit_code = None
        try:
            container.start()
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
            except Exception as exc:
                # On Windows requests may wrap urllib3's read timeout in a ConnectionError.
                if not _is_wait_timeout(exc):
                    raise
                timed_out = True
                container.kill()
            output, length = _read_log(container)
            return SandboxResult(exit_code=exit_code, output=output, timed_out=timed_out,
                                 original_length=length)
        finally:
            container.remove(force=True)

