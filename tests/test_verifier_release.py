from types import SimpleNamespace

from scripts.verify_step9 import find_later_release


class Client:
    def get(self, *args, **kwargs):
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: [
            {'tag_name': 'v2.3.0', 'draft': False, 'prerelease': False},
            {'tag_name': '2.1.0', 'draft': False, 'prerelease': False},
            {'tag_name': '2.0.1', 'draft': True, 'prerelease': False},
            {'tag_name': '2.0.2rc1', 'draft': False, 'prerelease': True},
            {'tag_name': '1.0.0', 'draft': False, 'prerelease': False},
        ])


def test_selects_first_later_stable_release():
    assert find_later_release(Client(), 'example/repo', '2.0.0') == '2.1.0'


def test_missing_or_unknown_version_never_guesses():
    assert find_later_release(Client(), 'example/repo', None) is None
    assert find_later_release(Client(), 'example/repo', 'main') is None
