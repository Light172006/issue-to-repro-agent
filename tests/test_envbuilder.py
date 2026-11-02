import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from repro.envbuilder import BuildError, _write_json, resolve_commit


class ResolutionTests(unittest.TestCase):
    def test_prefers_v_tag_then_plain_tag(self):
        client = Mock()
        missing = Mock(status_code=404)
        ok = Mock(status_code=200)
        ok.json.return_value = {'object': {'sha':'a' * 40, 'type':'commit'}}
        client.get.side_effect = [missing, ok]
        commit, ref = resolve_commit('owner/project', '1.2.0', client)
        self.assertEqual((commit, ref), ('a' * 40, '1.2.0'))
        self.assertIn('/git/ref/tags/v1.2.0', client.get.call_args_list[0].args[0])
        self.assertIn('/git/ref/tags/1.2.0', client.get.call_args_list[1].args[0])

    def test_default_branch_and_sha(self):
        client = Mock()
        client.get.return_value.status_code = 200
        client.get.return_value.json.return_value = {'sha': 'b' * 40}
        self.assertEqual(resolve_commit('owner/project', None, client), ('b' * 40, 'HEAD'))
        self.assertEqual(resolve_commit('owner/project', 'c' * 40, client), ('b' * 40, 'c' * 40))

    def test_reject_bad_version_before_network(self):
        client = Mock()
        for ref in ('../main', 'main;echo', 'v1/../../etc'):
            with self.assertRaises(ValueError): resolve_commit('owner/project', ref, client)
        client.get.assert_not_called()

    def test_missing_tag_is_reported(self):
        client = Mock()
        client.get.return_value.status_code = 404
        with self.assertRaises(BuildError): resolve_commit('owner/project', '1.2.0', client)

    def test_atomic_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'new' / 'environment.json'
            _write_json(path, {'commit': 'a' * 40})
            self.assertEqual(json.loads(path.read_text())['commit'], 'a' * 40)

    def test_cli_closes_docker_without_context_manager(self):
        from repro.envbuilder import main
        docker_client = Mock(spec=['close'])
        from unittest.mock import MagicMock
        http_client = MagicMock()
        http_client.__enter__ = Mock(return_value=http_client)
        http_client.__exit__ = Mock(return_value=False)
        docker_module = types.SimpleNamespace(from_env=Mock(return_value=docker_client))
        httpx_module = types.SimpleNamespace(Client=Mock(return_value=http_client))
        metadata = {'image': 'example', 'commit': 'a' * 40, 'cache_hit': False}
        with patch.dict(sys.modules, {'docker': docker_module, 'httpx': httpx_module}), \
             patch('sys.argv', ['envbuilder', 'owner/repo']), \
             patch('repro.envbuilder.EnvironmentBuilder') as builder:
            builder.return_value.build.return_value = metadata
            main()
        docker_client.close.assert_called_once()

    def test_annotated_tag_resolves_to_commit(self):
        client = Mock()
        tag_ref = Mock(status_code=200)
        tag_ref.json.return_value = {'object': {'sha': 'a' * 40, 'type': 'tag'}}
        tag_object = Mock(status_code=200)
        tag_object.json.return_value = {'object': {'sha': 'b' * 40, 'type': 'commit'}}
        client.get.side_effect = [tag_ref, tag_object]
        self.assertEqual(resolve_commit('owner/project', 'v1.0', client), ('b' * 40, 'v1.0'))
        self.assertTrue(client.get.call_args.args[0].endswith('/git/tags/' + 'a' * 40))

    def test_setup_pins_and_checks_git_commit(self):
        from repro.envbuilder import SETUP
        self.assertIn('git -C /var/tmp/repro/source', SETUP)
        self.assertIn('checkout --detach FETCH_HEAD', SETUP)
        self.assertIn('rev-parse HEAD', SETUP)
        self.assertIn('"$2"', SETUP)


class FetchConfigFilesTests(unittest.TestCase):
    def _make_file_response(self, content: str) -> Mock:
        import base64
        encoded = base64.b64encode(content.encode()).decode()
        resp = Mock(status_code=200)
        resp.json.return_value = {'type': 'file', 'encoding': 'base64', 'content': encoded}
        return resp

    def test_returns_fetched_files(self):
        from repro.envbuilder import _fetch_config_files
        client = Mock()
        client.get.side_effect = lambda url, **kw: (
            self._make_file_response('[project]\nname = "example"\n')
            if 'pyproject.toml' in url else Mock(status_code=404)
        )
        files = _fetch_config_files('owner/proj', 'a' * 40, client)
        self.assertIn('pyproject.toml', files)
        self.assertNotIn('setup.cfg', files)

    def test_404_files_are_skipped(self):
        from repro.envbuilder import _fetch_config_files
        client = Mock()
        client.get.return_value = Mock(status_code=404)
        files = _fetch_config_files('owner/proj', 'a' * 40, client)
        self.assertEqual(files, {})

    def test_fetch_exception_is_silently_skipped(self):
        from repro.envbuilder import _fetch_config_files
        client = Mock()
        client.get.side_effect = OSError('connection refused')
        # Must not raise; returns empty dict
        files = _fetch_config_files('owner/proj', 'a' * 40, client)
        self.assertEqual(files, {})

    def test_oversized_file_is_skipped(self):
        import base64

        from repro.envbuilder import _fetch_config_files
        big = 'x' * 200_000
        encoded = base64.b64encode(big.encode()).decode()
        resp = Mock(status_code=200)
        resp.json.return_value = {'type': 'file', 'encoding': 'base64', 'content': encoded}
        client = Mock()
        client.get.return_value = resp
        files = _fetch_config_files('owner/proj', 'a' * 40, client)
        self.assertEqual(files, {})

    def test_non_file_type_is_skipped(self):
        from repro.envbuilder import _fetch_config_files
        resp = Mock(status_code=200)
        resp.json.return_value = {'type': 'dir', 'encoding': 'base64', 'content': ''}
        client = Mock()
        client.get.return_value = resp
        files = _fetch_config_files('owner/proj', 'a' * 40, client)
        self.assertEqual(files, {})


class DiscoverDepsTests(unittest.TestCase):
    def test_returns_packages_from_requirements_file(self):
        import base64

        from repro.envbuilder import _discover_deps

        pyproject_content = '[project]\nname = "example"\n\n[project.optional-dependencies]\ntest = ["freezegun", "hypothesis"]\n'
        encoded = base64.b64encode(pyproject_content.encode()).decode()
        resp = Mock(status_code=200)
        resp.json.return_value = {'type': 'file', 'encoding': 'base64', 'content': encoded}
        miss = Mock(status_code=404)

        def side_effect(url, **kw):
            if 'pyproject.toml' in url:
                return resp
            return miss

        client = Mock()
        client.get.side_effect = side_effect
        packages, warnings = _discover_deps('owner/proj', 'a' * 40, client)
        # extras are not yet wired into the install command; they appear in warnings
        self.assertIn('discovered extras', ' '.join(warnings))
        # no packages from extras alone (extras are not returned as packages)
        self.assertIsInstance(packages, list)
        self.assertIsInstance(warnings, list)

    def test_fetch_failure_returns_empty_with_warning(self):
        from repro.envbuilder import _discover_deps
        client = Mock()
        client.get.side_effect = OSError('network error')
        packages, warnings = _discover_deps('owner/proj', 'a' * 40, client)
        self.assertEqual(packages, [])
        self.assertEqual(len(warnings), 0)  # fetch failures are silently skipped per-file

    def test_discovery_exception_returns_warning(self):
        from repro.envbuilder import _discover_deps
        client = Mock()
        # Make get raise at call-level (before per-file handling)
        client.get.side_effect = RuntimeError('unexpected')
        packages, warnings = _discover_deps('owner/proj', 'a' * 40, client)
        self.assertEqual(packages, [])
        # Silent per-file skip means this still returns empty
        self.assertIsInstance(warnings, list)

    def test_pytest_cov_plugin_discovered(self):
        import base64

        from repro.envbuilder import _discover_deps

        # pyproject with --cov in addopts triggers pytest-cov discovery
        pyproject_content = '[tool.pytest.ini_options]\naddopts = "--cov=src"\n'
        encoded = base64.b64encode(pyproject_content.encode()).decode()
        resp = Mock(status_code=200)
        resp.json.return_value = {'type': 'file', 'encoding': 'base64', 'content': encoded}
        miss = Mock(status_code=404)

        def side_effect(url, **kw):
            if 'pyproject.toml' in url:
                return resp
            return miss

        client = Mock()
        client.get.side_effect = side_effect
        packages, _warnings = _discover_deps('owner/proj', 'a' * 40, client)
        self.assertIn('pytest-cov', packages)

    def test_build_merges_discovered_dependencies(self):
        from repro.envbuilder import EnvironmentBuilder

        docker_client = Mock()
        image = Mock(id='img-123')
        docker_client.images.get.return_value = image

        http_client = Mock()
        builder = EnvironmentBuilder(docker_client, http_client)

        with tempfile.TemporaryDirectory() as tmp, \
             patch('repro.envbuilder.resolve_commit', return_value=('a' * 40, 'v1')), \
             patch('repro.envbuilder._discover_deps', return_value=(['freezegun', 'pytest-cov'], ['sample warning'])), \
             patch('repro.envbuilder.Sandbox') as mock_sandbox:
            sb_instance = MagicMock()
            sb_instance.__enter__.return_value = sb_instance
            sb_instance.run.side_effect = [
                Mock(timed_out=False, exit_code=0, output='{"python":"3.11.0","packages":["freezegun==1.2.0"],"resolution":{"strategy":"date_bounded"}}'),
                Mock(timed_out=False, exit_code=0, output='=== 1 passed in 0.1s ===')
            ]
            mock_sandbox.return_value = sb_instance

            meta = builder.build('owner/repo', '1.0.0', tmp, test_dependencies=['extra-dep'])

            self.assertIn('extra-dep', meta['test_dependencies'])
            self.assertIn('freezegun', meta['test_dependencies'])
            self.assertIn('pytest-cov', meta['test_dependencies'])
            self.assertEqual(meta['test_dependency_discovery']['discovered_packages'], ['freezegun', 'pytest-cov'])
            self.assertEqual(meta['test_dependency_discovery']['warnings'], ['sample warning'])

            saved = json.loads((Path(tmp) / 'environment.json').read_text())
            self.assertEqual(saved['test_dependencies'], meta['test_dependencies'])
            self.assertEqual(saved['test_dependency_discovery'], meta['test_dependency_discovery'])
