import pytest

from repro.github import fetch_issue


@pytest.mark.network
def test_public_issue_live(tmp_path):
    issue, path = fetch_issue('https://github.com/encode/httpx/issues/3433', tmp_path)
    assert issue['number'] == 3433 and issue['title'] and path.is_file()
