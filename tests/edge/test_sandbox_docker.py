import os
import pytest
from repro.sandbox import Sandbox

pytestmark = [pytest.mark.docker, pytest.mark.skipif(os.getenv('REPRO_DOCKER_TESTS') != '1', reason='set REPRO_DOCKER_TESTS=1')]

def test_binary_and_background_cleanup():
    import docker
    client=docker.from_env()
    try:
        before={c.id for c in client.containers.list(all=True)}
        box=Sandbox(client=client)
        result=box.run(['sh','-c','sleep 30 & printf "\\377"; wait'],timeout=2)
        assert result.timed_out
        assert '\ufffd' in result.output
        after={c.id for c in client.containers.list(all=True)}
        assert after == before
    finally: client.close()

def test_network_disabled_ipv4_ipv6():
    with Sandbox() as box:
        code = '''import socket
for family,address in [(socket.AF_INET,('1.1.1.1',443)), (socket.AF_INET6,('2606:4700:4700::1111',443))]:
 try:
  s=socket.socket(family); s.settimeout(2); s.connect(address)
 except OSError: continue
 raise SystemExit('unexpected network access')
'''
        r=box.run(['python','-c',code],timeout=10)
        assert r.exit_code == 0, r.output
