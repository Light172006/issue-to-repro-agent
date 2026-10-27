import unittest
from unittest.mock import Mock, patch

from repro.sandbox import Sandbox

class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.client = Mock()
        self.container = self.client.containers.create.return_value
        self.container.wait.return_value = {'StatusCode': 0}
        self.container.logs.return_value = b'hello\n'
        self.sandbox = Sandbox(client=self.client)

    def test_run_is_nonroot_and_network_disabled(self):
        result = self.sandbox.run(['echo', 'hello'])
        args, kwargs = self.client.containers.create.call_args
        self.assertEqual(kwargs['network_mode'], 'none')
        self.assertEqual(kwargs['user'], '65534:65534')
        self.assertEqual(kwargs['cap_drop'], ['ALL'])
        self.assertTrue(kwargs['read_only'])
        self.assertEqual(kwargs['pids_limit'], 128)
        self.assertFalse(kwargs['use_config_proxy'])
        self.assertEqual(result.output, 'hello\n')
        self.container.remove.assert_called_once_with(force=True)

    def test_setup_is_explicitly_networked(self):
        self.sandbox.run_setup(['python', '--version'])
        self.assertEqual(self.client.containers.create.call_args.kwargs['network_mode'], 'bridge')

    def test_validation_precedes_container_creation(self):
        for command, timeout in [([], 1), ('echo hello', 1), (['echo'], 61)]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                self.sandbox.run(command, timeout=timeout)
        self.client.containers.create.assert_not_called()

    def test_cleanup_when_wait_fails(self):
        self.container.wait.side_effect = RuntimeError('docker failure')
        with patch('repro.sandbox._is_wait_timeout', return_value=False), self.assertRaises(RuntimeError):
            self.sandbox.run(['echo', 'hello'])
        self.container.remove.assert_called_once_with(force=True)

    def test_timeout_kills_and_cleans_container(self):
        self.container.wait.side_effect = TimeoutError('timed out')
        with patch('repro.sandbox._is_wait_timeout', return_value=True):
            result = self.sandbox.run(['sleep', '5'], timeout=1)
        self.assertTrue(result.timed_out)
        self.container.kill.assert_called_once()
        self.container.remove.assert_called_once_with(force=True)

    def test_windows_wrapped_read_timeout(self):
        from requests.exceptions import ConnectionError
        from urllib3.exceptions import ReadTimeoutError
        self.container.wait.side_effect = ConnectionError(ReadTimeoutError(None, None, 'Read timed out'))
        result = self.sandbox.run(['sleep', '5'], timeout=1)
        self.assertTrue(result.timed_out)
        self.container.kill.assert_called_once()
        self.container.remove.assert_called_once_with(force=True)

    def test_unrelated_connection_error_is_not_timeout(self):
        from requests.exceptions import ConnectionError
        self.container.wait.side_effect = ConnectionError('connection refused')
        with self.assertRaises(ConnectionError):
            self.sandbox.run(['sleep', '5'], timeout=1)
        self.container.kill.assert_not_called()
        self.container.remove.assert_called_once_with(force=True)
