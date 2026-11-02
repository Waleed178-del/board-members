#!/usr/bin/env python3
"""Wrap board_room.html (artifact source, no document skeleton) into index.html for any static server.

    python3 demo/build_standalone.py
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "board_room.html").read_text(encoding="utf-8").replace('<meta charset="utf-8">\n', "", 1)
head, sep, body = src.partition("</style>")
page = (
    "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
    "<style>html{color-scheme:light dark}body{margin:0}[hidden]{display:none!important}</style>\n"
    + head + sep + "\n</head>\n<body>\n" + body.lstrip("\n") + "\n</body>\n</html>\n"
)
(HERE / "index.html").write_text(page, encoding="utf-8")
print(f"wrote {HERE / 'index.html'} ({len(page.encode())} bytes)")
