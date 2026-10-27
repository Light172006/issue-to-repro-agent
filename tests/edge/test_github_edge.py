import json
import hashlib
import pytest
import httpx
from repro.github import fetch_issue, parse_issue_url

def client():
    def respond(req):
        if req.url.path.endswith('/comments'):
            return httpx.Response(200, json=[{'id':1,'body':None,'user':None}])
        return httpx.Response(200, json={'title':'🧪','body':None,'labels':[]})
    return httpx.Client(transport=httpx.MockTransport(respond))

@pytest.mark.parametrize('invalid', ['', 'http://github.com/a/b/issues/1', 'https://u:p@github.com/a/b/issues/1', 'https://github.com/a/b/pull/1', 'https://github.com/a/b/issues/0', 'https://github.com/a/b/issues/1?q=2'])
def test_invalid_urls_rejected(invalid):
    with pytest.raises(ValueError): parse_issue_url(invalid)

@pytest.mark.parametrize('content', ['{', '', 'null', '[]', '{"schema_version": 1, "repo": 2}'])
def test_corrupt_cache_recovered(tmp_path, content):
    (tmp_path/(hashlib.sha256(b'a/b#1').hexdigest()+'.json')).write_text(content)
    with client() as c: data, _ = fetch_issue('https://github.com/a/b/issues/1', tmp_path, client=c)
    assert data['title'] == '🧪' and data['comments'][0]['author'] is None

def test_cache_collision_same_owner_dashes(tmp_path):
    with client() as c:
        _, first = fetch_issue('https://github.com/a--b/c/issues/1', tmp_path, client=c)
        _, second = fetch_issue('https://github.com/a/b--c/issues/1', tmp_path, client=c)
    assert first != second

@pytest.mark.parametrize('status', [401,403,404,410,429,500])
def test_http_failure_is_safe_and_does_not_cache(tmp_path,status):
    from repro.github import IssueFetchError
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(status, request=req))) as c:
        with pytest.raises(IssueFetchError,match=str(status)):
            fetch_issue('https://github.com/a/b/issues/1', tmp_path, token='sentinel-secret', client=c)
    assert list(tmp_path.iterdir()) == []

def test_interrupted_write_leaves_no_cache(tmp_path, monkeypatch):
    import repro.github as gh
    def fail(*args): raise OSError('no space')
    monkeypatch.setattr(gh.os, 'replace', fail)
    with client() as c, pytest.raises(OSError): fetch_issue('https://github.com/a/b/issues/1',tmp_path,client=c)
    assert list(tmp_path.iterdir()) == []
