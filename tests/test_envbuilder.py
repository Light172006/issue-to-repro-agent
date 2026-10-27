import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
import sys
import types

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
