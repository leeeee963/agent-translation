"""Desktop entry point: launches FastAPI in a background thread and opens a native window."""

from __future__ import annotations

import platform
import socket
import sys
import threading
import time
from pathlib import Path


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_server(port: int) -> None:
    import uvicorn

    uvicorn.run(
        "src.server:app",
        host="127.0.0.1",
        port=port,
        log_level="info",
    )


def _wait_for_server(port: int, timeout: float = 15.0) -> bool:
    import urllib.request
    import urllib.error

    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
            if r.status == 200:
                return True
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.1)
    return False


class DesktopApi:
    """Exposed to JavaScript as window.pywebview.api."""

    def __init__(self, port: int) -> None:
        self._port = port
        self._downloads_dir = Path.home() / "Downloads"

    def _unique_path(self, filename: str) -> Path:
        """Return a path in ~/Downloads/, adding (1), (2) etc. if name exists."""
        path = self._downloads_dir / filename
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        i = 1
        while path.exists():
            path = self._downloads_dir / f"{stem} ({i}){suffix}"
            i += 1
        return path

    def save_file_from_url(self, url_path: str) -> str:
        """Fetch a file from the local server and save to ~/Downloads/."""
        import urllib.request

        try:
            full_url = f"http://127.0.0.1:{self._port}{url_path}"
            resp = urllib.request.urlopen(full_url, timeout=30)
            data = resp.read()

            filename = url_path.rstrip("/").split("/")[-1]
            save_path = self._unique_path(filename)
            save_path.write_bytes(data)
            return str(save_path)
        except Exception as e:
            print(f"[DesktopApi] save_file_from_url error: {e}", file=sys.stderr)
            return ""

    def save_content(self, content: str, filename: str) -> str:
        """Save text content (e.g. review HTML) to ~/Downloads/."""
        try:
            save_path = self._unique_path(filename)
            save_path.write_text(content, encoding="utf-8")
            return str(save_path)
        except Exception as e:
            print(f"[DesktopApi] save_content error: {e}", file=sys.stderr)
            return ""


def main() -> None:
    from src.utils.paths import initialize_user_data

    initialize_user_data()

    port = _find_free_port()

    server_thread = threading.Thread(target=_start_server, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_server(port):
        print("Server failed to start within 15 seconds.", file=sys.stderr)
        sys.exit(1)

    import webview

    api = DesktopApi(port)
    webview.create_window(
        "AgentTranslation",
        f"http://127.0.0.1:{port}",
        width=1280,
        height=800,
        min_size=(800, 600),
        js_api=api,
    )
    if platform.system() == "Windows":
        webview.start(gui="edgechromium")
    else:
        webview.start()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        log_path = Path.home() / "AgentTranslation_error.log"
        log_path.write_text(traceback.format_exc(), encoding="utf-8")
        sys.exit(1)
