from __future__ import annotations

import http.server
import socketserver
from pathlib import Path


PORT = 8765


class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main() -> None:
    root = Path(__file__).resolve().parent
    handler = lambda *args, **kwargs: Handler(*args, directory=str(root), **kwargs)
    with socketserver.TCPServer(("127.0.0.1", PORT), handler) as httpd:
        print(f"ECG BLE GUI: http://127.0.0.1:{PORT}/index.html")
        print("Press Ctrl+C to stop.")
        httpd.serve_forever()


if __name__ == "__main__":
    main()
