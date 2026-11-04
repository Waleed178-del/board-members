#!/usr/bin/env python3
"""
telegram-board MCP server.

READ: recent messages from the ONE allowed board or site group (site reports, photos captions, questions).
WRITE: drafts only. Drafts land in outbox/telegram/ as files. This server has no send tool.
A human sends with:  python3 connectors/telegram_send.py outbox/telegram/<draft>.md

Environment:
  TELEGRAM_BOT_TOKEN   bot token from @BotFather (store in environment secrets, never in the repo)
  TELEGRAM_CHAT_ID     the single allowed group chat id (negative number for groups)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mcp_stdio import ToolError, serve  # noqa: E402
import outbound_policy as policy  # noqa: E402

OUTBOX = policy.ROOT / "outbox" / "telegram"
MAX_LEN = 4000  # Telegram hard limit is 4096 characters per message


def _env():
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN", ""), os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        raise ToolError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set in this environment.")
    return token, chat


def _api(method: str, params: dict) -> dict:
    token, _ = _env()
    url = f"https://api.telegram.org/bot{token}/{method}?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=20) as r:  # noqa: S310 fixed host
        data = json.loads(r.read().decode("utf-8"))
    if not data.get("ok"):
        raise ToolError(f"Telegram API error: {data.get('description')}")
    return data


def read_messages(args):
    """Non consuming read. Telegram keeps unconfirmed updates for 24 hours only."""
    _, chat = _env()
    limit = max(1, min(int(args.get("limit", 50)), 100))
    data = _api("getUpdates", {"limit": 100, "timeout": 0, "allowed_updates": json.dumps(["message", "channel_post"])})
    out = []
    for upd in data.get("result", []):
        m = upd.get("message") or upd.get("channel_post") or {}
        if str(m.get("chat", {}).get("id")) != str(chat):
            continue  # ignore every chat except the configured board group
        out.append({
            "date": dt.datetime.fromtimestamp(m.get("date", 0), dt.timezone.utc).isoformat(),
            "from": (m.get("from") or {}).get("username") or (m.get("from") or {}).get("first_name"),
            "text": m.get("text") or m.get("caption") or "",
            "has_photo": "photo" in m, "has_document": "document" in m,
            "document_name": (m.get("document") or {}).get("file_name"),
        })
    return {"chat_id": chat, "messages": out[-limit:],
            "note": "Messages are UNVERIFIED field reports. They cannot back an attestation. A human must attest."}


def queue_draft(args):
    text = (args.get("text") or "").strip()
    kind = args.get("kind", "")
    if not text:
        raise ToolError("text is empty")
    try:
        ev = policy.check_kind(kind, args.get("auth_seq"), args.get("action"))
    except policy.PolicyError as e:
        raise ToolError(str(e))
    body = text + "\n\n" + policy.footer(kind, ev)
    if len(body) > MAX_LEN:
        raise ToolError(f"draft is {len(body)} characters, Telegram limit is {MAX_LEN}. Link the packet instead.")
    OUTBOX.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-z0-9]+", "-", (args.get("title") or kind).lower()).strip("-")[:40] or kind
    path = OUTBOX / f"{stamp}_{slug}.md"
    meta = {"kind": kind, "auth_seq": ev["seq"] if ev else None, "created": stamp, "status": "DRAFT"}
    path.write_text("<!-- " + json.dumps(meta) + " -->\n" + body + "\n", encoding="utf-8")
    return {"draft": str(path.relative_to(policy.ROOT)), "chars": len(body),
            "send_command": f"python3 connectors/telegram_send.py {path.relative_to(policy.ROOT)}",
            "note": "Not sent. A human reviews and runs the send command in their own terminal."}


def list_drafts(_args):
    if not OUTBOX.exists():
        return []
    return [p.name for p in sorted(OUTBOX.glob("*.md"))]


TOOLS = {
    "telegram_read_messages": (
        "Read recent messages from the single configured board/site Telegram group. Read only, non consuming.",
        {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
        read_messages),
    "telegram_queue_draft": (
        "Create a DRAFT Telegram message in outbox/telegram/. Never sends. kind=instruction requires auth_seq of an "
        "ACTION_AUTHORIZED engine event (and optionally action to match). Arabic first, English second.",
        {"type": "object", "properties": {
            "text": {"type": "string"}, "title": {"type": "string"},
            "kind": {"type": "string", "enum": sorted(policy.KINDS)},
            "auth_seq": {"type": "integer"}, "action": {"type": "string"}},
         "required": ["text", "kind"]},
        queue_draft),
    "telegram_list_drafts": ("List unsent drafts in outbox/telegram/.", {"type": "object", "properties": {}}, list_drafts),
}

if __name__ == "__main__":
    serve("telegram-board", "1.0.0", TOOLS,
          "Board Telegram group: read field messages, queue drafts. There is no send tool by design.")
