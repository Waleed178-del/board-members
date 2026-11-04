#!/usr/bin/env python3
"""
m365-drafts MCP server. WRITE side of Microsoft 365, drafts only.

Tools
  outlook_create_draft     Draft email in the signed in user's Drafts folder. Cannot send (no Mail.Send scope).
  calendar_create_hold     Tentative event in the user's own calendar, no attendees, so no invitations go out.
  onedrive_upload_draft    Upload a packet or report into OneDrive /Apps/<app>/ (AppFolder scope only).

READ side (SharePoint, OneDrive search, Outlook search, Teams, calendar availability) is the official
Microsoft 365 connector in claude.ai.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mcp_stdio import ToolError, serve  # noqa: E402
import m365_auth  # noqa: E402
import outbound_policy as policy  # noqa: E402

GRAPH = "https://graph.microsoft.com/v1.0"
UPLOAD_DIRS = ("packets", "reports")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _graph(method: str, path: str, body=None, raw: bytes | None = None, ctype="application/json") -> dict:
    try:
        token = m365_auth.access_token()
    except m365_auth.AuthError as e:
        raise ToolError(str(e))
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(GRAPH + path, data=data, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 fixed host
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        raise ToolError(f"Graph {e.code}: {e.read().decode()[:400]}")


def _addresses(lst, field):
    lst = lst or []
    bad = [a for a in lst if not EMAIL_RE.match(a)]
    if bad:
        raise ToolError(f"invalid {field} address(es): {bad}")
    return [{"emailAddress": {"address": a}} for a in lst]


def _policy(args):
    try:
        return policy.check_kind(args.get("kind", ""), args.get("auth_seq"), args.get("action"))
    except policy.PolicyError as e:
        raise ToolError(str(e))


def create_draft(args):
    ev = _policy(args)
    body_html = args.get("body_html") or "<pre>" + html.escape(args.get("body_text", "")) + "</pre>"
    body_html += f"<p style='color:#888;font-size:11px'>{html.escape(policy.footer(args['kind'], ev))}</p>"
    msg = {
        "subject": args.get("subject", "").strip() or "(no subject)",
        "body": {"contentType": "HTML", "content": body_html},
        "toRecipients": _addresses(args.get("to"), "to"),
        "ccRecipients": _addresses(args.get("cc"), "cc"),
    }
    res = _graph("POST", "/me/messages", msg)
    return {"draft_id": res.get("id"), "web_link": res.get("webLink"), "status": "DRAFT_NOT_SENT",
            "note": "Saved in Outlook Drafts. A human reviews and presses Send."}


def create_hold(args):
    _policy({**args, "kind": args.get("kind", "meeting_notice")})
    ev = {
        "subject": args["subject"],
        "body": {"contentType": "Text", "content": args.get("body", "") + "\n\n[board:hold] Created as a draft hold."},
        "start": {"dateTime": args["start"], "timeZone": args.get("time_zone", "Asia/Damascus")},
        "end": {"dateTime": args["end"], "timeZone": args.get("time_zone", "Asia/Damascus")},
        "showAs": "tentative", "isReminderOn": True, "responseRequested": False,
        "attendees": [],  # never invite: invitations are sends
    }
    if args.get("location"):
        ev["location"] = {"displayName": args["location"]}
    res = _graph("POST", "/me/events", ev)
    return {"event_id": res.get("id"), "web_link": res.get("webLink"),
            "note": "Tentative hold in your calendar only. Add attendees yourself to invite."}


def upload_draft(args):
    rel = args.get("path", "")
    p = (policy.ROOT / rel).resolve()
    if p.parent.name not in UPLOAD_DIRS or p.parent.parent != policy.ROOT or not p.is_file():
        raise ToolError(f"Only files directly inside {UPLOAD_DIRS} can be uploaded.")
    data = p.read_bytes()
    if len(data) > 4 * 1024 * 1024:
        raise ToolError("File over 4 MB. Upload it by hand.")
    if b"[[UNVERIFIED]]" in data:
        raise ToolError("File carries [[UNVERIFIED]]. It cannot leave the repository as a board document.")
    name = urllib.parse.quote(f"{p.parent.name}/{p.name}")
    res = _graph("PUT", f"/me/drive/special/approot:/{name}:/content", raw=data, ctype="text/markdown")
    return {"item_id": res.get("id"), "web_url": res.get("webUrl"),
            "note": "Uploaded to the app folder only. Share it yourself from OneDrive."}


TOOLS = {
    "outlook_create_draft": (
        "Create an Outlook DRAFT (never sent). kind=instruction requires auth_seq of an ACTION_AUTHORIZED engine event.",
        {"type": "object", "properties": {
            "subject": {"type": "string"}, "to": {"type": "array", "items": {"type": "string"}},
            "cc": {"type": "array", "items": {"type": "string"}},
            "body_html": {"type": "string"}, "body_text": {"type": "string"},
            "kind": {"type": "string", "enum": sorted(policy.KINDS)},
            "auth_seq": {"type": "integer"}, "action": {"type": "string"}},
         "required": ["subject", "kind"]},
        create_draft),
    "calendar_create_hold": (
        "Create a tentative calendar hold with NO attendees (no invitations). Times ISO 8601 local, default Asia/Damascus.",
        {"type": "object", "properties": {
            "subject": {"type": "string"}, "start": {"type": "string"}, "end": {"type": "string"},
            "time_zone": {"type": "string"}, "location": {"type": "string"}, "body": {"type": "string"}},
         "required": ["subject", "start", "end"]},
        create_hold),
    "onedrive_upload_draft": (
        "Upload a decision packet or reconciliation report (packets/ or reports/) to the OneDrive app folder.",
        {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        upload_draft),
}

if __name__ == "__main__":
    if not os.environ.get("M365_CLIENT_ID"):
        sys.stderr.write("m365-drafts: M365_CLIENT_ID not set. Tools will refuse until configured.\n")
    serve("m365-drafts", "1.0.0", TOOLS, "Microsoft 365 drafts only. Nothing this server does reaches another person.")
