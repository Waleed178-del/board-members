#!/usr/bin/env python3
"""
Serve the board room simulator locally, or copy it into a project.

    python3 serve_demo.py                 # serve on the first free port from 8000
    python3 serve_demo.py --port 8100
    python3 serve_demo.py --copy demo/    # write demo/index.html into the current project instead

The page loads React and fonts from public CDNs, so the viewing browser needs internet access.
"""
import argparse
import functools
import http.server
import shutil
import socket
import socketserver
import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"


def free_port(start: int) -> int:
    for port in range(start, start + 50):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    sys.exit("No free port found")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--copy", metavar="DIR")
    a = ap.parse_args()
    page = ASSETS / "index.html"
    if a.copy:
        dst = Path(a.copy)
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(page, dst / "index.html")
        print(f"Copied simulator to {dst / 'index.html'}")
        return 0
    port = free_port(a.port)
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ASSETS))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("0.0.0.0", port), handler) as httpd:
        print(f"Board room simulator: http://localhost:{port}/  (Ctrl+C to stop)", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
