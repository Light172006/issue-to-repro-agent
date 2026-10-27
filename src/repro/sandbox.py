"""Run one command per isolated, disposable Docker container."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SandboxResult:
    exit_code: int | None
    output: str
    timed_out: bool


class Sandbox:
    """Local Docker sandbox. Uses Linux containers and never mounts host files.

    Each invocation creates a fresh container. Changes do not persist to the next
    invocation; image construction and run output mounts are later-step work.
    """
    def __init__(self, image: str = 'python:3.11-slim', *, client=None,
                 memory: str = '512m', nano_cpus: int = 1_000_000_000,
                 pids_limit: int = 128, max_timeout: float = 60):
        if nano_cpus <= 0 or pids_limit <= 0 or max_timeout <= 0:
            raise ValueError('CPU, process and timeout limits must be positive')
        if client is None:
            import docker
            client = docker.from_env()
            self._owns_client = True
        else:
            self._owns_client = False
        self.client = client
        self.image = image
        self.memory = memory
        self.nano_cpus = nano_cpus
        self.pids_limit = pids_limit
        self.max_timeout = max_timeout

    def close(self):
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
        if (not isinstance(command, (list, tuple)) or not command or
                any(not isinstance(arg, str) or not arg for arg in command)):
            raise ValueError('command must be a non-empty list of non-empty strings')
        if timeout <= 0 or timeout > self.max_timeout:
            raise ValueError('timeout must be positive and within the sandbox maximum')
        container = self.client.containers.create(
            self.image, command=list(command), user='65534:65534',
            network_mode=network_mode, mem_limit=self.memory,
            nano_cpus=self.nano_cpus, pids_limit=self.pids_limit,
            cap_drop=['ALL'], security_opt=['no-new-privileges:true'],
            read_only=True, tmpfs={'/tmp': 'rw,noexec,nosuid,size=64m'},
            working_dir='/tmp', environment={'HOME': '/tmp', 'PYTHONDONTWRITEBYTECODE': '1'},
            use_config_proxy=False, init=True,
        )
        timed_out = False
        exit_code = None
        try:
            container.start()
            try:
                result = container.wait(timeout=timeout)
                exit_code = result['StatusCode']
            except Exception as exc:
                # Docker SDK uses requests timeout exceptions for wait timeouts.
                import requests
                if not isinstance(exc, requests.exceptions.Timeout):
                    raise
                timed_out = True
                container.kill()
            output = container.logs(stdout=True, stderr=True, tail=1000).decode('utf-8', errors='replace')
            if len(output) > 32_000:
                output = output[:16_000] + '\n... output truncated ...\n' + output[-16_000:]
            return SandboxResult(exit_code=exit_code, output=output, timed_out=timed_out)
        finally:
            container.remove(force=True)
