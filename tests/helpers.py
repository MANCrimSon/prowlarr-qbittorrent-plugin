# Mock nova3 helpers for testing

def download_file(url: str) -> str:
    return f"/tmp/mock_downloaded_{hash(url)}.torrent"

def enable_socks_proxy(enable: bool) -> None:
    pass
