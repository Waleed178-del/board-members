"""
Microsoft identity platform helpers (device code flow, refresh tokens). Standard library only.

SCOPES are deliberately narrow. There is NO Mail.Send and NO Files.ReadWrite:
  Mail.ReadWrite             create drafts (cannot send without Mail.Send)
  Calendars.ReadWrite        create tentative holds in the signed in user's own calendar
  Files.ReadWrite.AppFolder  write only inside OneDrive /Apps/<app name>/
Reading SharePoint, Outlook and Teams is done by the official Microsoft 365 connector in claude.ai, not here.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

SCOPES = "offline_access Mail.ReadWrite Calendars.ReadWrite Files.ReadWrite.AppFolder"
TOKEN_PATH = Path(os.environ.get("M365_TOKEN_PATH", Path.home() / ".board-m365" / "token.json"))


class AuthError(Exception):
    pass


def _cfg():
    tenant, client = os.environ.get("M365_TENANT_ID", ""), os.environ.get("M365_CLIENT_ID", "")
    if not tenant or not client:
        raise AuthError("M365_TENANT_ID and M365_CLIENT_ID are not set.")
    return tenant, client


def _post(url: str, form: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(form).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 fixed host
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}")


def _save(tok: dict) -> None:
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(TOKEN_PATH.parent, 0o700)
    tok["expires_at"] = int(time.time()) + int(tok.get("expires_in", 3600)) - 120
    TOKEN_PATH.write_text(json.dumps(tok))
    os.chmod(TOKEN_PATH, 0o600)


def device_login(print_fn=print) -> None:
    tenant, client = _cfg()
    base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
    dc = _post(f"{base}/devicecode", {"client_id": client, "scope": SCOPES})
    if "device_code" not in dc:
        raise AuthError(f"device code request failed: {dc.get('error_description', dc)}")
    print_fn(dc["message"])
    deadline = time.time() + int(dc.get("expires_in", 900))
    while time.time() < deadline:
        time.sleep(int(dc.get("interval", 5)))
        tok = _post(f"{base}/token", {"grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                                      "client_id": client, "device_code": dc["device_code"]})
        if "access_token" in tok:
            _save(tok)
            return
        if tok.get("error") not in ("authorization_pending", "slow_down"):
            raise AuthError(tok.get("error_description", str(tok)))
    raise AuthError("device login timed out")


def access_token() -> str:
    if not TOKEN_PATH.exists():
        raise AuthError("Not signed in. A human must run: python3 connectors/m365_login.py")
    tok = json.loads(TOKEN_PATH.read_text())
    if time.time() < tok.get("expires_at", 0):
        return tok["access_token"]
    tenant, client = _cfg()
    new = _post(f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token",
                {"grant_type": "refresh_token", "client_id": client, "scope": SCOPES,
                 "refresh_token": tok.get("refresh_token", "")})
    if "access_token" not in new:
        raise AuthError("Session expired. A human must run: python3 connectors/m365_login.py")
    if "refresh_token" not in new:
        new["refresh_token"] = tok.get("refresh_token")
    _save(new)
    return new["access_token"]
