"""Mock HTTP 429 and 5xx responses for the Notion sync client. No network."""

import io
import unittest
import urllib.error
from email.message import EmailMessage
from unittest import mock

import notion_sync


class Response:
    def __init__(self, body):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def http_error(url, code, retry_after=None):
    headers = EmailMessage()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(url, code, "error", headers, io.BytesIO(b""))


class RetryTests(unittest.TestCase):
    def test_retries_429_then_succeeds_and_honors_retry_after(self):
        calls = {"n": 0}

        def urlopen(req, timeout=60):
            calls["n"] += 1
            if calls["n"] < 3:
                raise http_error(req.full_url, 429, "2")
            return Response(b'{"ok": true}')

        with mock.patch.object(notion_sync.urllib.request, "urlopen", urlopen), \
             mock.patch.object(notion_sync.time, "sleep") as sleep, \
             mock.patch.object(notion_sync.random, "random", return_value=0):
            result = notion_sync.http_json("https://api.notion.com/v1/blocks/x")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls["n"], 3)
        self.assertEqual(sleep.call_count, 2)
        self.assertEqual(sleep.call_args_list[0].args[0], 2.0)

    def test_retries_503_with_exponential_backoff(self):
        calls = {"n": 0}

        def urlopen(req, timeout=60):
            calls["n"] += 1
            if calls["n"] == 1:
                raise http_error(req.full_url, 503)
            return Response(b'{"ok": 1}')

        with mock.patch.object(notion_sync.urllib.request, "urlopen", urlopen), \
             mock.patch.object(notion_sync.time, "sleep") as sleep, \
             mock.patch.object(notion_sync.random, "random", return_value=0):
            notion_sync.http_json("https://www.notion.so/api/v3/loadPageChunk", {"page": {}})
        self.assertEqual(calls["n"], 2)
        self.assertEqual(sleep.call_args_list[0].args[0], 1.0)

    def test_does_not_retry_404(self):
        def urlopen(req, timeout=60):
            raise http_error(req.full_url, 404)

        with mock.patch.object(notion_sync.urllib.request, "urlopen", urlopen), \
             mock.patch.object(notion_sync.time, "sleep") as sleep:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                notion_sync.http_json("https://api.notion.com/v1/pages/missing")
        self.assertEqual(caught.exception.code, 404)
        sleep.assert_not_called()

    def test_gives_up_after_max_attempts(self):
        calls = {"n": 0}

        def urlopen(req, timeout=60):
            calls["n"] += 1
            raise http_error(req.full_url, 429, "0")

        with mock.patch.object(notion_sync.urllib.request, "urlopen", urlopen), \
             mock.patch.object(notion_sync.time, "sleep"), \
             mock.patch.object(notion_sync.random, "random", return_value=0):
            with self.assertRaises(urllib.error.HTTPError):
                notion_sync.http_json("https://api.notion.com/v1/blocks/x")
        self.assertEqual(calls["n"], notion_sync.MAX_HTTP_ATTEMPTS)

    def test_official_file_url_does_not_call_public_endpoint(self):
        seen = []

        def urlopen(req, timeout=60):
            seen.append(req.full_url)
            return Response(b'{"type":"file","file":{"url":"https://files.example/a.mp4"}}')

        block = {"id": "abc", "properties": {"source": [["attachment:uuid:a.mp4"]]}}
        with mock.patch.dict(notion_sync.os.environ, {"NOTION_TOKEN": "secret"}), \
             mock.patch.object(notion_sync.urllib.request, "urlopen", urlopen):
            url = notion_sync.signed_url(block)
        self.assertEqual(url, "https://files.example/a.mp4")
        self.assertTrue(seen[0].startswith("https://api.notion.com/v1/blocks/abc"))
        self.assertFalse(any("notion.so/api/v3" in item for item in seen))

    def test_public_file_url_used_only_without_token(self):
        seen = []

        def urlopen(req, timeout=60):
            seen.append(req.full_url)
            return Response(b'{"signedUrls":["https://signed.example/a.mp4"]}')

        block = {"id": "abc", "properties": {"source": [["attachment:uuid:a.mp4"]]}}
        with mock.patch.dict(notion_sync.os.environ, {"NOTION_TOKEN": ""}), \
             mock.patch.object(notion_sync.urllib.request, "urlopen", urlopen):
            url = notion_sync.signed_url(block)
        self.assertEqual(url, "https://signed.example/a.mp4")
        self.assertIn("getSignedFileUrls", seen[0])

    def test_retry_after_http_date(self):
        when = notion_sync.parse_retry_after(
            "Wed, 21 Oct 2015 07:28:00 GMT",
            now=notion_sync.datetime(2015, 10, 21, 7, 27, 0, tzinfo=notion_sync.timezone.utc),
        )
        self.assertEqual(when, 60.0)


if __name__ == "__main__":
    unittest.main()
