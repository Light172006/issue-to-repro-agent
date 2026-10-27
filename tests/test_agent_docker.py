"""Real Docker checks; run explicitly after installing Docker Desktop."""
import pytest

from repro.sandbox import Sandbox


@pytest.mark.docker
def test_repro_mount_persists_across_isolated_containers(tmp_path):
    path = tmp_path / 'runs' / 'mount-test' / 'repro'
    with Sandbox(image='python:3.11-slim', writable_mount=path) as box:
        written = box.run(['/usr/local/bin/python', '-c',
                           ("import os; assert os.getuid() != 0; "
                           "open('/work/repro/test.txt', 'w').write('hello')")])
        assert not written.timed_out and written.exit_code == 0, written.output
        read = box.run(['/usr/local/bin/python', '-c',
                        "assert open('/work/repro/test.txt').read() == 'hello'"])
        assert not read.timed_out and read.exit_code == 0, read.output
