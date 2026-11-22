import datetime
import json
import os
import sys
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import prowlarr
from prowlarr import _parse_iso_date, _get_browser_user_agent, _ProxyManager


class TestProwlarrPlugin(unittest.TestCase):
    def test_parse_iso_date(self):
        # UTC with Z
        ts1 = _parse_iso_date("2024-03-15T12:00:00Z")
        self.assertGreater(ts1, 0)
        dt1 = datetime.datetime.fromtimestamp(ts1, tz=datetime.timezone.utc)
        self.assertEqual(dt1.year, 2024)
        self.assertEqual(dt1.month, 3)
        self.assertEqual(dt1.day, 15)
        self.assertEqual(dt1.hour, 12)

        # With milliseconds and Z
        ts2 = _parse_iso_date("2024-03-15T12:00:00.123456Z")
        self.assertEqual(ts1, ts2)

        # With timezone offset
        ts3 = _parse_iso_date("2024-03-15T15:00:00+03:00")
        self.assertEqual(ts1, ts3)

        # Empty or invalid dates
        self.assertEqual(_parse_iso_date(None), -1)
        self.assertEqual(_parse_iso_date(""), -1)
        self.assertEqual(_parse_iso_date("invalid-date-string"), -1)

    def test_get_browser_user_agent(self):
        ua = _get_browser_user_agent()
        self.assertTrue(ua.startswith("Mozilla/5.0"))
        self.assertIn("Firefox/", ua)

    def test_escape_pipe(self):
        engine = prowlarr.prowlarr()
        sample = {
            'name': 'Movie | 2024 | 1080p | Remux',
            'desc_link': 'https://example.com/item?a=1|2',
            'seeds': 10,
            'size': '1024 B'
        }
        escaped = engine.escape_pipe(sample)
        self.assertEqual(escaped['name'], 'Movie %7C 2024 %7C 1080p %7C Remux')
        self.assertEqual(escaped['desc_link'], 'https://example.com/item?a=1%7C2')
        self.assertEqual(escaped['seeds'], 10)

    @patch('prowlarr.prowlarr.get_response')
    def test_search_results_mapping(self, mock_get_response):
        mock_releases = [
            {
                "guid": "guid-123",
                "title": "Ubuntu 24.04 LTS Desktop",
                "size": 6000000000,
                "indexer": "RuTracker",
                "indexerFlags": ["G_Freeleech"],
                "publishDate": "2024-04-25T10:00:00Z",
                "downloadUrl": "http://127.0.0.1:9696/download/123",
                "magnetUrl": "magnet:?xt=urn:btih:ubuntu123",
                "infoUrl": "https://rutracker.org/forum/viewtopic.php?t=123",
                "seeders": 150,
                "leechers": 10,
                "protocol": "torrent"
            },
            {
                "guid": "guid-usenet",
                "title": "Ubuntu Usenet Release",
                "size": 5000000000,
                "indexer": "NZBGeek",
                "publishDate": "2024-04-25T10:00:00Z",
                "downloadUrl": "http://127.0.0.1:9696/download/nzb",
                "protocol": "usenet"
            }
        ]
        mock_get_response.return_value = json.dumps(mock_releases)

        engine = prowlarr.prowlarr()
        engine.api_key = "valid_test_key"
        engine.multithreaded = False
        engine.show_flags = True
        engine.filter_usenet = True

        captured_results = []
        engine.pretty_printer_thread_safe = lambda res: captured_results.append(res)

        engine.search("ubuntu", "all")

        # Usenet release should be skipped, leaving 1 result
        self.assertEqual(len(captured_results), 1)
        res = captured_results[0]

        # Check Freeleech flag before tracker at the end
        self.assertTrue(res['name'].endswith("[RuTracker]"))
        self.assertEqual(res['name'], "Ubuntu 24.04 LTS Desktop [Freeleech] [RuTracker]")

        # Check magnet preference
        self.assertEqual(res['link'], "magnet:?xt=urn:btih:ubuntu123")
        self.assertEqual(res['size'], "6000000000 B")
        self.assertEqual(res['seeds'], 150)
        self.assertEqual(res['leech'], 10)
        self.assertEqual(res['desc_link'], "https://rutracker.org/forum/viewtopic.php?t=123")
        self.assertGreater(res['pub_date'], 0)

    @patch('prowlarr.prowlarr.get_response')
    def test_unconfigured_api_key(self, mock_get_response):
        engine = prowlarr.prowlarr()
        engine.api_key = "YOUR_API_KEY_HERE"

        captured_errors = []
        engine.pretty_printer_thread_safe = lambda res: captured_errors.append(res)

        engine.search("test")
        self.assertEqual(len(captured_errors), 1)
        self.assertIn("API key is not configured", captured_errors[0]['name'])

    @patch('prowlarr.prowlarr.get_response')
    def test_multiline_title_sanitization(self, mock_get_response):
        raw_multiline = "CONTROL Resonant\n\nRemedy Entertainment\r\n\tРейтинг\n0.0\n\n2020\r\nОткрыть игру [2020]"
        mock_releases = [{
            "guid": "guid-multi",
            "title": raw_multiline,
            "size": 100000,
            "indexer": "Byrutop",
            "indexerFlags": ["Freeleech"],
            "publishDate": "2024-04-25T10:00:00Z",
            "downloadUrl": "http://127.0.0.1:9696/download/multi",
            "protocol": "torrent"
        }]
        mock_get_response.return_value = json.dumps(mock_releases)

        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"
        engine.multithreaded = False
        captured = []
        engine.pretty_printer_thread_safe = lambda res: captured.append(res)
        engine.search("control")

        self.assertEqual(len(captured), 1)
        name = captured[0]['name']
        self.assertNotIn('\n', name)
        self.assertNotIn('\r', name)
        self.assertNotIn('\t', name)
        self.assertIn("CONTROL Resonant Remedy Entertainment Рейтинг 0.0 2020 Открыть игру [2020] [Freeleech] [Byrutop]", name)

    def test_proxy_manager(self):
        pm = _ProxyManager()
        os.environ['http_proxy'] = 'http://testproxy:8080'
        os.environ['https_proxy'] = 'http://testproxy:8080'

        pm.enable_proxy(False)
        self.assertNotIn('http_proxy', os.environ)
        self.assertNotIn('https_proxy', os.environ)

        pm.enable_proxy(True)
        self.assertEqual(os.environ.get('http_proxy'), 'http://testproxy:8080')
        self.assertEqual(os.environ.get('https_proxy'), 'http://testproxy:8080')

        # Clean up
        pm.enable_proxy(False)


    def test_novaprinter_integration(self):
        import tests.novaprinter as mock_nova
        import tests.helpers as mock_helpers

        with patch.object(prowlarr, 'prettyPrinter', mock_nova.prettyPrinter), \
             patch.object(prowlarr, 'helpers', mock_helpers):

            mock_release = [{
                "guid": "guid-789",
                "title": "Interstellar (2014) BDRip 1080p | D",
                "size": 15000000000,
                "indexer": "KinoZal",
                "indexerFlags": ["Freeleech"],
                "publishDate": "2024-05-01T14:30:00Z",
                "downloadUrl": "http://127.0.0.1:9696/download/789",
                "magnetUrl": "magnet:?xt=urn:btih:interstellar789",
                "infoUrl": "https://kinozal.tv/details.php?id=789",
                "seeders": 42,
                "leechers": 5,
                "protocol": "torrent"
            }]

            engine = prowlarr.prowlarr()
            engine.api_key = "test_key"
            engine.multithreaded = False
            engine.get_response = MagicMock(return_value=json.dumps(mock_release))

            mock_nova.captured_output.clear()
            engine.search("Interstellar", "movies")

            self.assertEqual(len(mock_nova.captured_output), 1)
            raw_line = mock_nova.captured_output[0]
            parts = raw_line.split('|')
            self.assertEqual(len(parts), 8, f"Expected exactly 8 fields in nova output, got {len(parts)}: {raw_line}")

            link, quoted_name, size_str, seeds, leech, engine_url, desc_link, pub_date = parts
            self.assertEqual(link, "magnet:?xt=urn:btih:interstellar789")
            # The pipe in title should have been escaped before quoting or handled safely
            self.assertIn("Interstellar", quoted_name)
            self.assertEqual(size_str, "15000000000")
            self.assertEqual(seeds, "42")
            self.assertEqual(leech, "5")
            self.assertEqual(engine_url, "http://127.0.0.1:9696")
            self.assertEqual(desc_link, "https://kinozal.tv/details.php?id=789")
            self.assertTrue(int(pub_date) > 0)

    def test_http_401_diagnostics(self):
        import io
        engine = prowlarr.prowlarr()
        engine.api_key = "wrong_key"

        http_err = urllib.error.HTTPError("http://127.0.0.1:9696", 401, "Unauthorized", {}, io.BytesIO(b""))
        with patch('urllib.request.OpenerDirector.open', side_effect=http_err):
            res = engine.get_response("http://127.0.0.1:9696/api/v1/search")
            self.assertIsNone(res)
            self.assertIn("Invalid API key (HTTP 401 Unauthorized)", engine.last_error)

    def test_timeout_diagnostics(self):
        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"
        engine.timeout = 120

        url_err = urllib.error.URLError(TimeoutError("The read operation timed out"))
        with patch('urllib.request.OpenerDirector.open', side_effect=url_err):
            res = engine.get_response("http://127.0.0.1:9696/api/v1/search")
            self.assertIsNone(res)
            self.assertIn("Request timed out after 120s", engine.last_error)

    def test_connection_refused_diagnostics(self):
        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"

        url_err = urllib.error.URLError(ConnectionRefusedError("Connection refused"))
        with patch('urllib.request.OpenerDirector.open', side_effect=url_err):
            res = engine.get_response("http://127.0.0.1:9696/api/v1/search")
            self.assertIsNone(res)
            self.assertIn("Connection refused", engine.last_error)

    def test_html_response_diagnostics(self):
        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"
        engine.get_response = MagicMock(return_value="<html><body>Cloudflare Blocked</body></html>")

        captured = []
        engine.pretty_printer_thread_safe = lambda res: captured.append(res)
        engine.search("test")

        self.assertEqual(len(captured), 1)
        self.assertIn("Received HTML instead of JSON", captured[0]['name'])

    def test_multithreaded_search(self):
        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"
        engine.multithreaded = True
        engine.thread_count = 5

        called_urls = []
        def mock_fetch(url):
            called_urls.append(url)
            if "/api/v1/indexer" in url:
                return json.dumps([
                    {"id": 10, "name": "TrackerTen", "enable": True, "protocol": "torrent"},
                    {"id": 20, "name": "TrackerTwenty", "enable": True, "protocol": "torrent"},
                    {"id": 30, "name": "UsenetNZB", "enable": True, "protocol": "usenet"},
                    {"id": 40, "name": "DisabledTracker", "enable": False, "protocol": "torrent"}
                ]), None
            elif "indexerIds=10" in url:
                return json.dumps([{
                    "guid": "g-10",
                    "title": "Release from Tracker 10",
                    "size": 1000,
                    "indexer": "TrackerTen",
                    "downloadUrl": "http://127.0.0.1:9696/dl/10"
                }]), None
            elif "indexerIds=20" in url:
                return json.dumps([{
                    "guid": "g-20",
                    "title": "Release from Tracker 20",
                    "size": 2000,
                    "indexer": "TrackerTwenty",
                    "downloadUrl": "http://127.0.0.1:9696/dl/20"
                }]), None
            return "[]", None

        engine._fetch_response = MagicMock(side_effect=mock_fetch)
        captured = []
        engine.pretty_printer_thread_safe = lambda res: captured.append(res)
        engine.search("ubuntu")

        # Releases from TrackerTen and TrackerTwenty must both be captured
        self.assertEqual(len(captured), 2)
        names = [c['name'] for c in captured]
        self.assertTrue(any("TrackerTen" in n for n in names))
        self.assertTrue(any("TrackerTwenty" in n for n in names))
        # API key must not be exposed in query string
        for url in called_urls:
            self.assertNotIn("apikey=", url)

    def test_multithreaded_zero_active_indexers_no_fallback(self):
        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"
        engine.multithreaded = True
        engine.thread_count = 5

        called_urls = []
        def mock_fetch(url):
            called_urls.append(url)
            if "/api/v1/indexer" in url:
                return json.dumps([
                    {"id": 30, "name": "UsenetOnly", "enable": True, "protocol": "usenet"},
                    {"id": 40, "name": "DisabledTracker", "enable": False, "protocol": "torrent"},
                ]), None
            return "[]", None

        engine._fetch_response = MagicMock(side_effect=mock_fetch)
        captured = []
        engine.pretty_printer_thread_safe = lambda res: captured.append(res)
        engine.search("ubuntu")

        self.assertEqual(len(captured), 0)
        self.assertEqual(len(called_urls), 1)
        self.assertIn("/api/v1/indexer", called_urls[0])

    def test_multithreaded_all_indexers_failed_reports_error(self):
        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"
        engine.multithreaded = True
        engine.thread_count = 5

        def mock_fetch(url):
            if "/api/v1/indexer" in url:
                return json.dumps([
                    {"id": 10, "name": "TrackerTen", "enable": True, "protocol": "torrent"},
                ]), None
            return None, "Request timed out after 30s"

        engine._fetch_response = MagicMock(side_effect=mock_fetch)
        captured = []
        engine.pretty_printer_thread_safe = lambda res: captured.append(res)
        engine.search("ubuntu")

        self.assertEqual(len(captured), 1)
        self.assertIn("Request timed out after 30s", captured[0]['name'])

    def test_multithreaded_disabled_fallback(self):
        engine = prowlarr.prowlarr()
        engine.api_key = "valid_key"
        engine.multithreaded = False

        called_urls = []
        def mock_get(url):
            called_urls.append(url)
            return json.dumps([{
                "guid": "g-mono",
                "title": "Monolithic Release",
                "size": 5000,
                "indexer": "MonoTracker",
                "downloadUrl": "http://127.0.0.1:9696/dl/mono"
            }])

        engine.get_response = MagicMock(side_effect=mock_get)
        captured = []
        engine.pretty_printer_thread_safe = lambda res: captured.append(res)
        engine.search("ubuntu")

        self.assertEqual(len(captured), 1)
        self.assertIn("indexerIds=-2", called_urls[0])
        self.assertNotIn("apikey=", called_urls[0])

    def test_infohash_magnet_fallback(self):
        engine = prowlarr.prowlarr()
        item = {
            "title": "Debian 12 ISO",
            "indexer": "DHTIndexer",
            "infoHash": "0123456789abcdef0123456789abcdef01234567",
            "size": 700000000,
            "protocol": "torrent",
        }
        res = engine.format_release(item)
        self.assertIsNotNone(res)
        self.assertTrue(res['link'].startswith("magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567"))

    def test_safe_int_config_guard(self):
        self.assertEqual(prowlarr._safe_int("25", 10), 25)
        self.assertEqual(prowlarr._safe_int("invalid", 10), 10)
        self.assertEqual(prowlarr._safe_int(None, 30), 30)
        self.assertEqual(prowlarr._safe_int(True, 10), 10)
        self.assertEqual(prowlarr._safe_int(0, 10, min_val=1), 1)

    def test_download_torrent_single_request_and_no_api_key_leak(self):
        import io
        engine = prowlarr.prowlarr()
        engine.url = "http://127.0.0.1:9696"
        engine.api_key = "secret_prowlarr_key"

        captured_headers = {}

        class DummyResp:
            headers = {}
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self):
                return b"d8:announce19:http://example.com/e"

        def fake_open(req, timeout=None):
            captured_headers.update(dict(req.header_items()))
            return DummyResp()

        stdout_buf = io.StringIO()
        with patch('urllib.request.OpenerDirector.open', side_effect=fake_open), \
             patch('sys.stdout', stdout_buf):
            engine.download_torrent("https://external-tracker.example/file.torrent")

        # X-Api-Key must NOT be sent to external tracker URLs
        self.assertNotIn('X-api-key', captured_headers)
        self.assertNotIn('X-Api-Key', captured_headers)

        output = stdout_buf.getvalue().strip()
        tmp_path, orig_url = output.split(' ', 1)
        self.assertEqual(orig_url, "https://external-tracker.example/file.torrent")
        self.assertTrue(os.path.exists(tmp_path))
        try:
            with open(tmp_path, 'rb') as f:
                self.assertEqual(f.read(), b"d8:announce19:http://example.com/e")
        finally:
            os.unlink(tmp_path)

    def test_download_torrent_magnet_redirect(self):
        import io
        engine = prowlarr.prowlarr()
        engine.url = "http://127.0.0.1:9696"
        engine.api_key = "secret_prowlarr_key"

        magnet = "magnet:?xt=urn:btih:abcdef123456"
        http_err = urllib.error.HTTPError(
            "http://127.0.0.1:9696/1/download",
            302,
            "Found",
            {"Location": magnet},
            io.BytesIO(b""),
        )
        stdout_buf = io.StringIO()
        with patch('urllib.request.OpenerDirector.open', side_effect=http_err), \
             patch('sys.stdout', stdout_buf):
            engine.download_torrent("http://127.0.0.1:9696/1/download")

        self.assertEqual(stdout_buf.getvalue().strip(), f"{magnet} http://127.0.0.1:9696/1/download")


if __name__ == '__main__':
    unittest.main()
