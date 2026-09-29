# Modern Prowlarr Search Plugin for qBittorrent

A high-performance, modern search engine plugin for **qBittorrent** (nova3) integrating directly with **Prowlarr**.

---

## Key Features & Improvements over Legacy Plugins

- **Publication Date Support (`pub_date`)**: Converts Prowlarr ISO 8601 timestamps into POSIX timestamps so qBittorrent can sort search results by date.
- **Native REST API Integration**: Queries `/api/v1/search` with URL-encoded parameters (full Unicode, Cyrillic, and special characters support without query corruption).
- **Proxy Isolation (`_ProxyManager`)**: Automatically bypasses global HTTP/HTTPS and SOCKS proxies for local Prowlarr connections (`127.0.0.1`), eliminating loopback timeout issues while retaining proxy capability for external downloads.
- **Dynamic Modern User-Agent**: Generates real-browser headers to prevent reverse proxies (Nginx, Cloudflare) from blocking automated search requests.
- **Indexer Flags & Freeleech Badges**: Automatically detects and displays `[Freeleech]`, `[HalfFreeleech]`, and other tracker flags in the title.
- **Protocol Filtering**: Automatically discards Usenet releases (`.nzb`) to prevent broken downloads in qBittorrent.
- **Thread Safety**: Uses a thread lock (`Lock`) for output rendering, preventing mangled results when qBittorrent runs concurrent searches.
- **Direct Magnet & Download Support**: Seamlessly prioritizes direct magnet links and properly downloads proxied `.torrent` files via Prowlarr.

---

## Installation

### Method 1: Install from URL (Recommended)
1. In **qBittorrent**, go to the **Search** tab.
2. Click **Search plugins...** (bottom-right button).
3. Click **Install a new one** -> **Web link**.
4. Paste the raw link to `prowlarr.py`:
   ```text
   https://raw.githubusercontent.com/<YOUR_USER>/prowlarr-qbittorrent-plugin/main/prowlarr.py
   ```
5. Click **OK**.

### Method 2: Manual Installation
1. Locate your qBittorrent search engines directory:
   - **Windows**: `%localappdata%\qBittorrent\nova3\engines\`
     *(e.g., `C:\Users\<User>\AppData\Local\qBittorrent\nova3\engines\`)*
   - **Linux**: `~/.local/share/data/qBittorrent/nova3/engines/`
   - **macOS**: `~/Library/Application Support/qBittorrent/nova3/engines/`
2. Copy `prowlarr.py` into this folder.

---

## Configuration

Upon its first execution, the plugin will automatically create `prowlarr.json` in the same directory as `prowlarr.py`.

Open `prowlarr.json` in any text editor and configure your instance:

```json
{
    "api_key": "YOUR_PROWLARR_API_KEY",
    "filter_usenet": true,
    "flags_position": "end",
    "show_flags": true,
    "timeout_seconds": 60,
    "tracker_first": false,
    "url": "http://127.0.0.1:9696"
}
```

### Options Description
- `api_key`: Your Prowlarr API key. Find it in Prowlarr under **Settings** -> **General** -> **Security** -> **API Key**.
- `url`: The base URL where Prowlarr is accessible (default: `http://127.0.0.1:9696`). Do not include a trailing slash.
- `tracker_first`:
  - `false` (default): `Title [Tracker]`
  - `true`: `[Tracker] Title`
- `show_flags`:
  - `true` (default): Show `[Freeleech]` or other tracker tags.
  - `false`: Do not show flags.
- `flags_position`:
  - `"end"` (default): Append flags before tracker at the end (`Title [Freeleech] [Tracker]`), preserving alphabetical title sorting.
  - `"start"`: Prepend flags at the beginning (`[Freeleech] Title [Tracker]`).
- `filter_usenet`:
  - `true` (default): Filter out any Usenet releases returned by Prowlarr.
  - `false`: Include all results.
- `timeout_seconds`: Maximum time in seconds to wait for Prowlarr response (default: `60`).

---

## Running Tests

To verify that the plugin functions correctly:

```bash
python -m unittest discover tests
```

---

## License

MIT License.
