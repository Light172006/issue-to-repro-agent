"""Run real-Docker checks against an already-built environment image."""
from __future__ import annotations

import argparse
import os
import socket
import tempfile
from pathlib import Path

import docker

from repro.sandbox import Sandbox


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--image', required=True, help='Image recorded in environment.json')
    args = parser.parse_args()
    client = docker.from_env()
    results: list[tuple[str, bool, str]] = []

    def record(label: str, command: list[str], *, expected: int = 0, timeout: float = 20) -> None:
        try:
            result = sandbox.run(command, timeout=timeout)
            results.append((label, not result.timed_out and result.exit_code == expected,
                            result.output[-300:]))
        except (docker.errors.DockerException, OSError, ValueError, RuntimeError) as exc:
            results.append((label, False, type(exc).__name__))

    def py(code: str) -> list[str]:
        return ['/usr/local/bin/python', '-c', code]

    try:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'runs' / 'isolation' / 'repro'
            sandbox = Sandbox(args.image, client=client, writable_mount=path,
                              working_dir='/var/tmp/repro/source', max_timeout=30)
            try:
                record('non-root', py('import os; assert os.getuid() != 0'))
                record('write repro', py("open('/work/repro/persist.txt','w').write('persist')"))
                record('second container sees file', py("assert open('/work/repro/persist.txt').read() == 'persist'"))
                denied = "import errno; exec(\"try:\\n open(%r, 'w')\\nexcept OSError as e:\\n assert e.errno == errno.EROFS\\nelse:\\n raise AssertionError('write succeeded')\")"
                record('source is read-only', py(denied % '/var/tmp/repro/source/isolation-write-check'))
                record('root is read-only', py(denied % '/var/tmp/isolation-write-check'))
                record('DNS blocked', py("import socket; socket.getaddrinfo('example.com',80)"), expected=1)
                record('public IP blocked', py("import socket; socket.create_connection(('1.1.1.1',80),2)"), expected=1)
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1', 0))
                    listener.listen(1)
                    port = listener.getsockname()[1]
                    with socket.create_connection(('127.0.0.1', port), timeout=2):
                        connection, _ = listener.accept()
                        connection.close()
                    record('host localhost blocked',
                           py(f"import socket; socket.create_connection(('127.0.0.1',{port}),2)"),
                           expected=1)
                os.environ['REPRO_ISOLATION_SENTINEL'] = 'isolation-secret-sentinel'
                record('host environment hidden', py("import os; assert 'REPRO_ISOLATION_SENTINEL' not in os.environ and 'META_MODEL_API_KEY' not in os.environ and 'GITHUB_TOKEN' not in os.environ"))
                record('Docker socket absent', py("import os; assert not os.path.exists('/var/run/docker.sock')"))
                before = {item.id for item in client.containers.list(all=True)}
                try:
                    result = sandbox.run(py('import time; time.sleep(20)'), timeout=1)
                    after = {item.id for item in client.containers.list(all=True)}
                    results.append(('timeout and cleanup', result.timed_out and not (after - before), ''))
                except (docker.errors.DockerException, OSError, ValueError, RuntimeError) as exc:
                    results.append(('timeout and cleanup', False, type(exc).__name__))
                try:
                    result = sandbox.run(py("import os; b=b'x'*8192\nfor i in range(6400): os.write(1,b)"), timeout=30)
                    results.append(('50 MiB output truncated', result.exit_code == 0 and
                                    'truncated' in result.output and len(result.output) < 40000 and
                                    result.original_length == 50 * 1024 * 1024, ''))
                except (docker.errors.DockerException, OSError, ValueError, RuntimeError) as exc:
                    results.append(('50 MiB output truncated', False, type(exc).__name__))
            finally:
                sandbox.close()
                os.environ.pop('REPRO_ISOLATION_SENTINEL', None)
    finally:
        client.close()
    print('Check | Result | Detail')
    for label, passed, detail in results:
        print(f'{label} | {"PASS" if passed else "FAIL"} | {detail if not passed else ""}')
    return 0 if results and all(item[1] for item in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
