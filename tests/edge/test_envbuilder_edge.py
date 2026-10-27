from unittest.mock import Mock
import pytest
from repro.envbuilder import resolve_commit

@pytest.mark.parametrize('version', ['', ' ', '../x', 'v1/../../x'])
def test_empty_or_invalid_version_not_silent_default(version):
    client=Mock()
    with pytest.raises(ValueError): resolve_commit('owner/repo',version,client)
    client.get.assert_not_called()

def test_invalid_repo_cannot_escape():
    client=Mock()
    with pytest.raises(ValueError): resolve_commit('../repo',None,client)
    client.get.assert_not_called()
