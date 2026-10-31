"""Opt-in: run with REPRO_DOCKER_TESTS=1 and a running Linux Docker daemon."""
import os
import unittest

import pytest

pytestmark = pytest.mark.docker
from repro.sandbox import Sandbox


@unittest.skipUnless(os.getenv('REPRO_DOCKER_TESTS') == '1', 'set REPRO_DOCKER_TESTS=1')
class DockerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sandbox = Sandbox()
    @classmethod
    def tearDownClass(cls):
        cls.sandbox.close()

    def test_nonroot_and_command(self):
        result = self.sandbox.run(['python', '-c', 'import os; print(os.getuid()); print("hello")'])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output.splitlines(), ['65534', 'hello'])

    def test_timeout_kills_container(self):
        result = self.sandbox.run(['python', '-c', 'import time; time.sleep(30)'], timeout=2)
        self.assertTrue(result.timed_out)
        self.assertIsNone(result.exit_code)

    def test_network_is_disabled(self):
        code = ('import socket,sys; s=socket.socket(); s.settimeout(2); '
                'sys.exit(0 if s.connect_ex(("1.1.1.1", 443)) != 0 else 1)')
        result = self.sandbox.run(['python', '-c', code], timeout=10)
        self.assertEqual(result.exit_code, 0, result.output)

