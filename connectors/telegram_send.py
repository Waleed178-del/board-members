#!/usr/bin/env python3
"""
HUMAN ONLY. Send one reviewed Telegram draft to the board group.

    python3 connectors/telegram_send.py outbox/telegram/<draft>.md

Requires an interactive terminal and a typed confirmation. Agents have no terminal, so they cannot send.
Sent drafts move to outbox/telegram/sent/ with the Telegram message id appended.
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    try:
        tty = open("/dev/tty", "r+", encoding="utf-8")
    except OSError:
        print("REFUSED: human only. No interactive terminal.", file=sys.stderr)
        return 2
    if not sys.stdin.isatty():
        print("REFUSED: human only. stdin is not a terminal.", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    raw = path.read_text(encoding="utf-8")
    first, _, body = raw.partition("\n")
    meta = json.loads(first.removeprefix("<!-- ").removesuffix(" -->")) if first.startswith("<!--") else {}
    if meta.get("status") != "DRAFT":
        print("REFUSED: not a draft or already sent.", file=sys.stderr)
        return 2
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat:
        print("REFUSED: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set.", file=sys.stderr)
        return 2
    tty.write("=" * 60 + f"\nTo chat {chat}  kind={meta.get('kind')}  auth_seq={meta.get('auth_seq')}\n" + "=" * 60 + "\n")
    tty.write(body.strip() + "\n" + "=" * 60 + "\nType SEND to post, anything else to cancel: ")
    tty.flush()
    if tty.readline().strip() != "SEND":
        print("Cancelled.")
        return 0
    data = urllib.parse.urlencode({"chat_id": chat, "text": body.strip(), "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=20) as r:  # noqa: S310
        res = json.loads(r.read().decode("utf-8"))
    if not res.get("ok"):
        print(f"FAILED: {res.get('description')}", file=sys.stderr)
        return 3
    meta.update(status="SENT", message_id=res["result"]["message_id"])
    sent_dir = path.parent / "sent"
    sent_dir.mkdir(exist_ok=True)
    (sent_dir / path.name).write_text("<!-- " + json.dumps(meta) + " -->\n" + body, encoding="utf-8")
    path.unlink()
    print(f"SENT message_id={meta['message_id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
