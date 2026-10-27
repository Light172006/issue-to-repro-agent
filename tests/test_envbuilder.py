import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from repro.envbuilder import BuildError, _write_json, resolve_commit

class ResolutionTests(unittest.TestCase):
    def test_prefers_v_tag_then_plain_tag(self):
        client = Mock()
        missing = Mock(status_code=404)
        ok = Mock(status_code=200)
        ok.json.return_value = {'sha':'a' * 40}
        client.get.side_effect = [missing, ok]
        commit, ref = resolve_commit('owner/project', '1.2.0', client)
        self.assertEqual((commit, ref), ('a' * 40, '1.2.0'))
        self.assertIn('/commits/refs/tags/v1.2.0', client.get.call_args_list[0].args[0])
        self.assertIn('/commits/refs/tags/1.2.0', client.get.call_args_list[1].args[0])

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
