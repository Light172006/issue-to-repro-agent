import json
import tempfile
import unittest
from pathlib import Path

from repro.github import IssueFetchError, fetch_issue, parse_issue_url


class Response:
    def __init__(self, data, fail=False): self.data, self.fail = data, fail
    def raise_for_status(self):
        if self.fail: raise RuntimeError('failure')
    def json(self): return self.data

class Client:
    def __init__(self): self.calls = []
    def get(self, url, params=None):
        self.calls.append((url, params))
        if url.endswith('/comments'):
            page = params['page']
            return Response([{'id': i, 'body': 'log: https://example.com/log.txt', 'user': {'login':'reporter'}}
                             for i in range(100 if page == 1 else 1)])
        return Response({'title':'Bug', 'body':'Broken', 'labels':[{'name':'bug'}]})

class GitHubTests(unittest.TestCase):
    def test_urls(self):
        self.assertEqual(parse_issue_url('https://github.com/Owner/repo.py/issues/123/'), ('Owner','repo.py',123))
        for url in ('https://github.com/x/y/pull/1', 'http://github.com/x/y/issues/1',
                    'https://github.com.evil/x/y/issues/1', 'https://github.com/x/../issues/1',
                    'https://github.com/x/y/issues/0', 'https://github.com/x/y/issues/1?q=1'):
            with self.subTest(url=url), self.assertRaises(ValueError): parse_issue_url(url)

    def test_fetch_pages_cache_and_refresh(self):
        with tempfile.TemporaryDirectory() as d:
            client = Client()
            data, path = fetch_issue('https://github.com/Owner/repo/issues/7', d, client=client)
            self.assertEqual(len(data['comments']), 101)
            self.assertEqual(data['labels'], ['bug'])
            self.assertEqual(data['linked_urls'], ['https://example.com/log.txt'])
            self.assertEqual(json.loads(path.read_text(encoding='utf-8')), data)
            self.assertEqual(len(client.calls), 3)
            fetch_issue('https://github.com/owner/REPO/issues/7', d, client=client)
            self.assertEqual(len(client.calls), 3)
            fetch_issue('https://github.com/Owner/repo/issues/7', d, client=client, refresh=True)
            self.assertEqual(len(client.calls), 6)

    def test_pull_request_rejected(self):
        client = Client()
        client.get = lambda *args, **kwargs: Response({'pull_request': {}})
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(IssueFetchError):
                fetch_issue('https://github.com/a/b/issues/1', d, client=client)
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_failed_page_does_not_save(self):
        client = Client()
        client.get = lambda url, params=None: Response({}, fail=True)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(IssueFetchError): fetch_issue('https://github.com/a/b/issues/1', d, client=client)
            self.assertEqual(list(Path(d).iterdir()), [])
