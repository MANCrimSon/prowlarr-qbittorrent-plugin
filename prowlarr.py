# VERSION: 2.00
# AUTHORS: Modern Prowlarr Community Plugin
# CONTRIBUTORS:
#               swannie-eire (original v1.0 plugin)
#               Diego de las Heras (ngosang@hotmail.es)
#               hannsen (github.com/hannsen)
#               Alexander Georgievskiy <galeksandrp@gmail.com>

import datetime
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from threading import Lock
from typing import Any, Dict, List, Optional, Union

# qBittorrent nova3 runtime modules
try:
    import helpers
    from novaprinter import prettyPrinter
except ImportError:
    helpers = None  # type: ignore[assignment]
    prettyPrinter = None  # type: ignore[assignment]


###############################################################################
# Proxy Manager: prevents loopback connection failures when qBittorrent uses
# global HTTP/HTTPS/SOCKS proxy, while keeping proxy for external tracker downloads.
###############################################################################
class _ProxyManager:
    HTTP_PROXY_KEY = "http_proxy"
    HTTPS_PROXY_KEY = "https_proxy"

    def __init__(self) -> None:
        self.http_proxy = os.environ.get(self.HTTP_PROXY_KEY, "")
        self.https_proxy = os.environ.get(self.HTTPS_PROXY_KEY, "")

    def enable_proxy(self, enable: bool) -> None:
        if enable:
            if self.http_proxy:
                os.environ[self.HTTP_PROXY_KEY] = self.http_proxy
            if self.https_proxy:
                os.environ[self.HTTPS_PROXY_KEY] = self.https_proxy
        else:
            current_http = os.environ.get(self.HTTP_PROXY_KEY) or os.environ.get(self.HTTP_PROXY_KEY.upper())
            current_https = os.environ.get(self.HTTPS_PROXY_KEY) or os.environ.get(self.HTTPS_PROXY_KEY.upper())
            if current_http:
                self.http_proxy = current_http
            if current_https:
                self.https_proxy = current_https

            os.environ.pop(self.HTTP_PROXY_KEY, None)
            os.environ.pop(self.HTTPS_PROXY_KEY, None)
            os.environ.pop(self.HTTP_PROXY_KEY.upper(), None)
            os.environ.pop(self.HTTPS_PROXY_KEY.upper(), None)

        if helpers is not None:
            try:
                helpers.enable_socks_proxy(enable)
            except AttributeError:
                pass


_proxy_manager = _ProxyManager()
_proxy_manager.enable_proxy(False)


###############################################################################
# Configuration
###############################################################################
_CONFIG_FILE = 'prowlarr.json'
_CONFIG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), _CONFIG_FILE)
_CONFIG_DATA: Dict[str, Any] = {
    'api_key': 'YOUR_API_KEY_HERE',  # Prowlarr API key (Settings > General)
    'url': 'http://127.0.0.1:9696',  # Prowlarr instance URL
    'tracker_first': False,          # True: '[Tracker] Title', False: 'Title [Tracker]'
    'show_flags': True,              # True: Show '[Freeleech]' and other flags in release name
    'flags_position': 'end',         # 'end': 'Title [Tracker] [Freeleech]', 'start': '[Freeleech] Title [Tracker]'
    'filter_usenet': True,           # True: Ignore Usenet releases to avoid broken .nzb downloads
    'timeout_seconds': 60,           # HTTP request timeout in seconds
}
_PRINTER_THREAD_LOCK = Lock()


def _load_configuration() -> None:
    global _CONFIG_DATA
    try:
        with open(_CONFIG_PATH, 'r', encoding='utf-8') as f:
            loaded_data = json.load(f)
            if isinstance(loaded_data, dict):
                _CONFIG_DATA.update(loaded_data)
    except ValueError:
        _CONFIG_DATA['malformed'] = True
    except FileNotFoundError:
        _save_configuration()
    except Exception:
        _CONFIG_DATA['malformed'] = True

    # Validate essential configuration keys
    if any(item not in _CONFIG_DATA for item in ['api_key', 'url']):
        _CONFIG_DATA['malformed'] = True

    # Ensure all defaults are written to disk
    if not os.path.exists(_CONFIG_PATH):
        _save_configuration()


def _save_configuration() -> None:
    try:
        with open(_CONFIG_PATH, 'w', encoding='utf-8') as f:
            f.write(json.dumps(_CONFIG_DATA, indent=4, sort_keys=True))
    except Exception:
        pass


_load_configuration()


def _get_browser_user_agent() -> str:
    base_date = datetime.date(2024, 4, 16)
    base_version = 125
    now_date = datetime.datetime.now(datetime.timezone.utc).date()
    now_version = base_version + ((now_date - base_date).days // 30)
    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{now_version}.0) Gecko/20100101 Firefox/{now_version}.0"


def _parse_iso_date(date_str: Optional[str]) -> int:
    """Convert ISO 8601 date string to POSIX timestamp."""
    if not date_str:
        return -1
    try:
        # Standard ISO 8601 normalization (handle 'Z' suffix)
        normalized = date_str.strip().replace('Z', '+00:00')
        dt = datetime.datetime.fromisoformat(normalized)
        return int(dt.timestamp())
    except Exception:
        return -1


###############################################################################
# Prowlarr Search Engine
###############################################################################
class prowlarr:
    name = 'Prowlarr'
    url = _CONFIG_DATA.get('url', 'http://127.0.0.1:9696').rstrip('/')
    api_key = _CONFIG_DATA.get('api_key', 'YOUR_API_KEY_HERE')
    tracker_first = bool(_CONFIG_DATA.get('tracker_first', False))
    show_flags = bool(_CONFIG_DATA.get('show_flags', True))
    flags_position = str(_CONFIG_DATA.get('flags_position', 'end')).lower()
    filter_usenet = bool(_CONFIG_DATA.get('filter_usenet', True))
    timeout = int(_CONFIG_DATA.get('timeout_seconds', 60))

    # Torznab / Newznab categories supported by Prowlarr
    supported_categories = {
        'all': None,
        'anime': ['5070'],
        'books': ['8000'],
        'games': ['1000', '4000'],
        'movies': ['2000'],
        'music': ['3000'],
        'software': ['4000'],
        'tv': ['5000'],
    }

    def download_torrent(self, download_url: str) -> None:
        """Handle torrent or magnet download request from qBittorrent."""
        if download_url.startswith('magnet:?'):
            print(f"{download_url} {download_url}")
            return

        is_local_prowlarr = download_url.startswith(self.url)
        _proxy_manager.enable_proxy(not is_local_prowlarr)

        try:
            response = self.get_response(download_url)
        finally:
            _proxy_manager.enable_proxy(False)

        if response is not None and response.startswith('magnet:?'):
            print(f"{response} {download_url}")
        elif helpers is not None:
            print(helpers.download_file(download_url))
        else:
            print(download_url)

    def search(self, what: str, cat: str = 'all') -> None:
        what = urllib.parse.unquote(what).strip()
        cat_key = cat.lower()
        categories = self.supported_categories.get(cat_key)

        # Check configuration sanity
        if _CONFIG_DATA.get('malformed'):
            self.handle_error("Configuration file is malformed", what)
            return

        if self.api_key == "YOUR_API_KEY_HERE" or not self.api_key:
            self.handle_error("API key is not configured in prowlarr.json", what)
            return

        # Prepare Prowlarr REST API search query
        # indexerIds=-2 tells Prowlarr to query all enabled torrent indexers
        params_list: List[tuple[str, str]] = [
            ('query', what),
            ('type', 'search'),
            ('indexerIds', '-2'),
            ('apikey', self.api_key),
        ]

        if categories:
            for cat_id in categories:
                params_list.append(('categories', cat_id))

        query_string = urllib.parse.urlencode(params_list)
        search_endpoint = f"{self.url}/api/v1/search?{query_string}"

        _proxy_manager.enable_proxy(False)
        response_text = self.get_response(search_endpoint)

        if response_text is None:
            self.handle_error(f"Failed to connect to Prowlarr at {self.url}", what)
            return

        try:
            results = json.loads(response_text)
        except json.JSONDecodeError:
            self.handle_error("Invalid JSON response received from Prowlarr", what)
            return

        if not isinstance(results, list):
            # Check for Prowlarr error messages (e.g. {"message": "Unauthorized"})
            if isinstance(results, dict) and 'message' in results:
                self.handle_error(f"Prowlarr error: {results['message']}", what)
            else:
                self.handle_error("Unexpected response schema from Prowlarr", what)
            return

        for item in results:
            if not isinstance(item, dict):
                continue

            # Skip Usenet releases if configured
            protocol = str(item.get('protocol', '')).lower()
            if self.filter_usenet and (protocol == 'usenet' or protocol == '2'):
                continue

            raw_title = item.get('title')
            if not raw_title:
                continue

            # Sanitize title: replace newlines, carriage returns, tabs and collapse multiple spaces
            cleaned_title = re.sub(r'[\r\n\t]+', ' ', str(raw_title))
            cleaned_title = re.sub(r'\s{2,}', ' ', cleaned_title).strip()
            if not cleaned_title:
                continue

            indexer = item.get('indexer', 'Prowlarr')

            # Parse indexer flags (e.g. Freeleech, HalfFreeleech)
            flag_badge = ""
            if self.show_flags:
                indexer_flags = item.get('indexerFlags') or []
                clean_flags = []
                for f in indexer_flags:
                    f_name = str(f).replace('G_', '')
                    clean_flags.append(f_name)
                if clean_flags:
                    flag_badge = f"[{'/'.join(clean_flags)}]"

            # Format item name according to user preference (flags at the end by default)
            if self.flags_position == 'start' and flag_badge:
                if self.tracker_first:
                    formatted_name = f"{flag_badge} [{indexer}] {cleaned_title}"
                else:
                    formatted_name = f"{flag_badge} {cleaned_title} [{indexer}]"
            else:
                flag_suffix = f" {flag_badge}" if flag_badge else ""
                if self.tracker_first:
                    formatted_name = f"[{indexer}] {cleaned_title}{flag_suffix}"
                else:
                    formatted_name = f"{cleaned_title} [{indexer}]{flag_suffix}"

            # Determine download link: prefer magnetUrl, fallback to downloadUrl
            magnet_url = item.get('magnetUrl')
            download_url = item.get('downloadUrl')
            chosen_link = magnet_url if magnet_url else download_url

            if not chosen_link:
                continue

            # Size in bytes
            raw_size = item.get('size', -1)
            try:
                size_val = int(raw_size) if raw_size is not None else -1
            except (ValueError, TypeError):
                size_val = -1

            # Seeders and leechers
            raw_seeds = item.get('seeders')
            seeds = int(raw_seeds) if raw_seeds is not None and isinstance(raw_seeds, (int, str)) and str(raw_seeds).lstrip('-').isdigit() else -1

            raw_leech = item.get('leechers')
            leech = int(raw_leech) if raw_leech is not None and isinstance(raw_leech, (int, str)) and str(raw_leech).lstrip('-').isdigit() else -1

            # Description link / info
            desc_link = item.get('infoUrl') or item.get('commentUrl') or item.get('guid') or ''

            # Publication date as POSIX timestamp
            pub_date = _parse_iso_date(item.get('publishDate'))

            res: Dict[str, Any] = {
                'link': chosen_link,
                'name': formatted_name,
                'size': f"{size_val} B" if size_val >= 0 else -1,
                'seeds': seeds,
                'leech': leech,
                'engine_url': self.url,
                'desc_link': desc_link,
                'pub_date': pub_date,
            }

            self.pretty_printer_thread_safe(res)

    def get_response(self, query_url: str) -> Optional[str]:
        """Send HTTP GET request to Prowlarr API with proper headers and cookie handling."""
        try:
            req = urllib.request.Request(query_url)
            req.add_header('User-Agent', _get_browser_user_agent())
            req.add_header('X-Api-Key', self.api_key)
            req.add_header('Accept', 'application/json, text/plain, */*')

            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
            with opener.open(req, timeout=self.timeout) as resp:
                charset = resp.headers.get_content_charset() or 'utf-8'
                return resp.read().decode(charset, errors='replace')
        except urllib.error.HTTPError as e:
            # Handle 302/301 redirects to magnet links in download_torrent
            if e.code in (301, 302, 303, 307, 308):
                redirect_url = e.headers.get('Location')
                if redirect_url and redirect_url.startswith('magnet:?'):
                    return redirect_url
            return None
        except Exception:
            return None

    def handle_error(self, error_msg: str, what: str) -> None:
        """Report errors directly in the qBittorrent search results list."""
        self.pretty_printer_thread_safe({
            'link': self.url,
            'name': f"Prowlarr: {error_msg}! Config: '{_CONFIG_PATH}' Search: '{what}'",
            'size': -1,
            'seeds': -1,
            'leech': -1,
            'engine_url': self.url,
            'desc_link': 'https://wiki.servarr.com/prowlarr',
            'pub_date': -1,
        })

    def pretty_printer_thread_safe(self, dictionary: Dict[str, Any]) -> None:
        """Output escaped search result securely under mutex lock."""
        escaped_dict = self.escape_pipe(dictionary)
        with _PRINTER_THREAD_LOCK:
            if prettyPrinter is not None:
                prettyPrinter(escaped_dict)
            else:
                # Standalone fallback output
                name = escaped_dict.get('name')
                link = escaped_dict.get('link')
                size = escaped_dict.get('size')
                seeds = escaped_dict.get('seeds')
                leech = escaped_dict.get('leech')
                pub_date = escaped_dict.get('pub_date')
                print(f"[{seeds}/{leech}] {name} ({size}) [pubDate:{pub_date}] -> {link}")

    def escape_pipe(self, dictionary: Dict[str, Any]) -> Dict[str, Any]:
        """Escape pipe delimiter '|' from values to protect nova3 stream protocol."""
        sanitized = {}
        for key, value in dictionary.items():
            if isinstance(value, str):
                sanitized[key] = value.replace('|', '%7C')
            else:
                sanitized[key] = value
        return sanitized


if __name__ == "__main__":
    test_search = sys.argv[1] if len(sys.argv) > 1 else "ubuntu"
    test_cat = sys.argv[2] if len(sys.argv) > 2 else "all"
    prowlarr_engine = prowlarr()
    prowlarr_engine.search(test_search, test_cat)

