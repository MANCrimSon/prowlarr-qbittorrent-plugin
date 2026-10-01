# Modern Prowlarr Search Plugin for qBittorrent

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![qBittorrent nova3](https://img.shields.io/badge/qBittorrent-nova3-green.svg)](https://github.com/qbittorrent/search-plugins)

A high-performance, modernized search engine plugin for **qBittorrent** (nova3) integrating directly with **Prowlarr**.

Maintained by **[MANCrimSon](https://github.com/MANCrimSon)**.

---

## Key Features & Improvements

- **Progressive Multi-Threaded Search**: Queries all enabled indexers concurrently with configurable worker threads (`thread_count`), delivering instant search results in 1–2 seconds without waiting for slow or unresponsive trackers.
- **Publication Date Support (`pub_date`)**: Converts Prowlarr ISO 8601 timestamps into POSIX timestamps so qBittorrent correctly displays and sorts releases by publication date.
- **Tracker Flags & Freeleech Badges**: Automatically detects and displays `[Freeleech]`, `[halfleech]`, and other tracker flags right next to the tracker tag (e.g. `Release Title [Freeleech] [RuTracker]`).
- **Alphabetical Sorting Preservation**: Badges and tracker tags are placed cleanly at the end of the title, allowing natural alphabetical sorting by release name.
- **Multiline Title Sanitization**: Automatically strips harmful newline characters (`\r\n`, `\n`, `\t`) and collapses redundant spaces returned by certain indexers (like Byrutor, Catorrent), keeping all rows perfectly single-line and preventing UI table row distortion.
- **Proxy Isolation (`_ProxyManager`)**: Automatically bypasses global HTTP/HTTPS and SOCKS proxies for local/internal Prowlarr connections (`127.0.0.1` / local subnet), eliminating loopback timeout issues while retaining proxy capability for external downloads.
- **Granular Network Diagnostics**: Clear, specific error reporting identifying socket timeouts, connection refused, reverse proxy issues (HTTP 401, 403, 404, 500, 502, 504), and HTML captive portal / Cloudflare block detection.
- **Native REST API Integration**: Queries `/api/v1/search` with URL-encoded parameters (full Unicode, Cyrillic, and special characters support without query corruption).
- **Usenet Filtering (`filter_usenet`)**: Automatically discards Usenet releases (`.nzb`) to prevent broken downloads in qBittorrent.
- **Dynamic Modern User-Agent**: Generates real-browser headers to prevent reverse proxies (Nginx, Cloudflare) from blocking automated search requests.
- **Thread Safety**: Uses a mutex lock (`Lock`) and escapes pipe characters (`|`) to ensure stream stability under concurrent search engines.
- **Windows UTF-8 Encoding Safeguard**: Configures stdout stream decoding to prevent `UnicodeEncodeError` when dealing with titles containing uncommon characters.

---

## Installation

### Method 1: Install from URL in qBittorrent (Recommended)
1. In **qBittorrent**, go to the **Search** tab.
2. Click the **Search plugins...** button (bottom-right).
3. Click **Install a new one** -> **Web link**.
4. Paste the following URL:
   ```text
   https://raw.githubusercontent.com/MANCrimSon/prowlarr-qbittorrent-plugin/main/prowlarr.py
   ```
5. Click **OK**. The plugin will be downloaded and enabled automatically.

### Method 2: Manual Installation
1. Locate your qBittorrent search engines directory:
   - **Windows**: `%localappdata%\qBittorrent\nova3\engines\`
     *(e.g., `C:\Users\<Username>\AppData\Local\qBittorrent\nova3\engines\`)*
   - **Linux**: `~/.local/share/data/qBittorrent/nova3/engines/`
   - **macOS**: `~/Library/Application Support/qBittorrent/nova3/engines/`
2. Copy `prowlarr.py` (and optionally `prowlarr.ico`) into this directory.

---

## Configuration (`prowlarr.json`)

Upon first execution, the plugin will automatically create `prowlarr.json` in the same directory as `prowlarr.py`.

Open `prowlarr.json` in any text editor to configure your connection:

```json
{
    "url": "http://127.0.0.1:9696",
    "api_key": "YOUR_PROWLARR_API_KEY",
    "multithreaded": true,
    "thread_count": 10,
    "timeout_seconds": 30,
    "filter_usenet": true,
    "tracker_first": false,
    "show_flags": true,
    "flags_position": "end"
}
```

### Configuration Parameters Reference

| Parameter | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `url` | `string` | `"http://127.0.0.1:9696"` | The URL where Prowlarr is accessible. Do not include a trailing slash. Can be `http://localhost:9696`, a local IP, or a remote server URL. |
| `api_key` | `string` | `"YOUR_API_KEY_HERE"` | Your Prowlarr API key. Found in Prowlarr WebUI under **Settings** &rarr; **General** &rarr; **Security** &rarr; **API Key**. |
| `multithreaded` | `boolean` | `true` | Enables concurrent multi-threaded indexer searching for progressive, instant results in qBittorrent. |
| `thread_count` | `integer` | `10` | Number of concurrent worker threads. 10 provides maximum search speed without high server CPU usage. |
| `timeout_seconds` | `integer` | `30` | HTTP request timeout in seconds. 30s allows individual indexers sufficient time to respond while preventing unresponsive indexers from hanging searches. |
| `filter_usenet` | `boolean` | `true` | Skips non-torrent (Usenet) releases returned by Prowlarr to avoid broken `.nzb` downloads in qBittorrent. |
| `tracker_first` | `boolean` | `false` | Determines tracker tag placement: <br>&bull; `false`: `Title [Tracker]`<br>&bull; `true`: `[Tracker] Title` |
| `show_flags` | `boolean` | `true` | Enables or disables displaying tracker flags (e.g., `[Freeleech]`, `[halfleech]`, `[DoubleUpload]`). |
| `flags_position` | `string` | `"end"` | Placement of the freeleech/indexer flags: <br>&bull; `"end"`: Appends flags before tracker at the end (`Title [Freeleech] [Tracker]`). Preserves alphabetical sorting.<br>&bull; `"start"`: Prepends flags at the beginning (`[Freeleech] Title [Tracker]`). |

---

## Running Unit Tests

This project includes a comprehensive test suite covering ISO 8601 parsing, title sanitization, proxy management, and `novaprinter` stream serialization:

```bash
python -m unittest discover tests
```

---

## Contributing

Pull requests, issue reports, and suggestions are welcome! Feel free to open an issue or submit a PR on [GitHub](https://github.com/MANCrimSon/prowlarr-qbittorrent-plugin).

## License

This project is licensed under the [MIT License](LICENSE).
