#!/usr/bin/env python3
"""
HUMAN ONLY. Sign the m365-drafts connector in to Microsoft 365 with the device code flow.

    python3 connectors/m365_login.py

Needs M365_TENANT_ID and M365_CLIENT_ID (an Entra ID app registration with "Allow public client flows" on,
delegated permissions Mail.ReadWrite, Calendars.ReadWrite, Files.ReadWrite.AppFolder, offline_access).
The refresh token is stored at ~/.board-m365/token.json with mode 600, outside the repository.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import m365_auth  # noqa: E402


def main() -> int:
    try:
        open("/dev/tty").close()
    except OSError:
        print("REFUSED: human only. No interactive terminal.", file=sys.stderr)
        return 2
    if not sys.stdin.isatty():
        print("REFUSED: human only. stdin is not a terminal.", file=sys.stderr)
        return 2
    try:
        m365_auth.device_login()
    except m365_auth.AuthError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        return 3
    print(f"Signed in. Token stored at {m365_auth.TOKEN_PATH}. Scopes: {m365_auth.SCOPES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
