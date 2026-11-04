# Connectors and Skills | الموصلات والمهارات

## Connector map

| App | Connector | Reads | Writes | Setup owner |
|---|---|---|---|---|
| Microsoft 365 | Official claude.ai connector | SharePoint, OneDrive, Outlook mail, calendar, Teams | nothing | M365 admin |
| Microsoft 365 | `m365-drafts` (local, this repo) | nothing | Outlook drafts, calendar holds with no attendees, OneDrive app folder | M365 admin |
| Telegram | `telegram-board` (local, this repo) | one board group | drafts in `outbox/telegram/` | Chair |
| Governance engine | `board-ledger` (local, this repo) | status, gates, dry run authorization, packets | nothing | none |

Sending always happens outside the agents: the Outlook Send button, or `python3 connectors/telegram_send.py <draft>`
in a human terminal.

## 1. Microsoft 365, read side (official connector)

1. A Microsoft 365 admin approves the Claude app for the tenant.
2. In claude.ai: Settings, Connectors, Microsoft 365, Connect. Sign in with the board account.
3. In tool permissions, keep everything read. The guard also blocks anything that is not read only.

## 2. Microsoft 365, drafts side (`m365-drafts`)

1. Entra ID admin center, App registrations, New registration. Name: `Board Drafts`. Single tenant.
2. Authentication: enable **Allow public client flows**.
3. API permissions, Microsoft Graph, **Delegated**: `Mail.ReadWrite`, `Calendars.ReadWrite`,
   `Files.ReadWrite.AppFolder`, `offline_access`. Do **not** add `Mail.Send` or `Files.ReadWrite`. Grant admin consent.
4. Put `M365_TENANT_ID` and `M365_CLIENT_ID` in the environment settings (cloud) or your shell profile (local).
   They are identifiers, not secrets, but keep them out of the repository.
5. A human signs in once, in their own terminal:

```bash
python3 connectors/m365_login.py
```

The refresh token is stored at `~/.board-m365/token.json` with mode 600. In a cloud session that file disappears
when the container is recycled, so the sign in is repeated per session.

## 3. Telegram (`telegram-board`)

1. In Telegram, talk to `@BotFather`, `/newbot`, keep the token.
2. Add the bot to the private board group. In BotFather run `/setprivacy` and choose Disable if the bot must read
   site reports. Otherwise it only sees commands and replies.
3. Find the group chat id (negative number), for example by sending a message in the group and reading
   `getUpdates` once in a browser.
4. Store `TELEGRAM_BOT_TOKEN` as a secret and `TELEGRAM_CHAT_ID` as a variable in the environment settings.
   Never commit them.
5. A human sends reviewed drafts:

```bash
python3 connectors/telegram_send.py outbox/telegram/<draft>.md
```

## 4. Board ledger (`board-ledger`)

No setup. It reads the engine. Board members on Claude Desktop can add it as a local MCP server pointing at
`connectors/board_ledger_mcp.py` in their checkout to ask "where are we" without a terminal.

## Skills

| Skill | Calculator | Used by |
|---|---|---|
| `extrusion-press-sizing` | `scripts/press_calc.py` | tech-spec-auditor |
| `spare-parts-planning` | | tech-spec-auditor |
| `contract-redlining` | | legal-counsel |
| `syrian-trade-finance` | | legal-counsel, fin-acct-controller |
| `capex-accounting-ifrs` | `scripts/depreciation.py` | fin-acct-controller |
| `critical-path-scheduling` | `scripts/cpm.py` | ops-logistics-coord, hr-planner |
| `bilingual-board-packet` | | all |
| `m365-document-intake` | | Board_Exec |
| `board-comms-drafting` | | Board_Exec |

## What each control does and does not stop

| Control | Stops | Does not stop |
|---|---|---|
| No `Mail.Send` scope | Any email leaving through `m365-drafts`, even if the code is changed | A human sending a bad draft |
| No Telegram send tool, tty only sender | Agents posting to the group | A human posting a bad draft |
| `auth_seq` check on instruction drafts | Drafting a payment or booking instruction the engine has not allowed | Mislabelling an instruction as `status_update`. Humans must read before sending |
| Guard MCP allowlist | Other connectors in the account (Gmail send, Drive share, SQL) being used from this project | Use of those connectors from other projects |
| Intake into the repo | Verdicts resting on documents that change later in SharePoint | A wrong document imported. Check the `.source.md` sidecar |
