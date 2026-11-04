---
name: board-comms-drafting
description: Draft outbound board communications through the connectors (Outlook drafts, calendar holds, OneDrive packet upload, Telegram outbox) under the drafts only rule. Use for gate alerts, status updates, meeting notices, vendor emails, claim notices and any instruction to a third party.
---

# Board Communications Drafting | صياغة المراسلات

## The rule
Agents create drafts. A human sends. No connector in this project has a send tool, and the guard hook blocks
any MCP tool whose name contains send, reply, forward, share, delete, publish or invite.

## Pick the kind
| kind | Examples | Needs engine authorization |
|---|---|---|
| `status_update` | weekly gate status, progress | No |
| `gate_alert` | veto, tamper, stale verdict, open discrepancy | No |
| `meeting_notice` | board meeting agenda, calendar hold | No |
| `instruction` | RFP release, vendor email committing us, payment order, booking request, pour order, claim notice | **Yes**: `auth_seq` of an ALLOW |

For `instruction`:
```bash
python3 engine/board.py authorize <action> [--ref <ref>]
```
Copy the event number from `ALLOW ... (event N)` into `auth_seq`, and pass `action` so the connector checks they
match. On DENY, do not draft. Report the unmet conditions instead.

## Pick the channel
| Audience | Channel | Tool |
|---|---|---|
| Board and site team, short alert | Telegram group | `telegram_queue_draft` → human runs `python3 connectors/telegram_send.py <draft>` |
| Vendor, contractor, bank, lawyer | Outlook | `outlook_create_draft` → human sends from Outlook |
| Board meeting | Outlook calendar | `calendar_create_hold` (no attendees) → human adds invitees |
| Packet for board reading | OneDrive app folder | `onedrive_upload_draft` → human shares |

## Content rules
- Arabic first, English second for internal messages (bilingual-board-packet). English only for foreign vendors.
- Telegram: under 1,500 characters, link or name the packet file. No bank details, no contract prices, no PINs.
- Email to third parties: never include internal verdicts, risk scores or negotiation positions unless that is the
  purpose of the email.
- Never put a file carrying `[[UNVERIFIED]]` into an outbound draft.

## After the human sends
Record the fact in the next packet (date, channel, recipient). Messages are not attestations. A sent claim notice
does not resolve a discrepancy. Only `resolve-discrepancy` with evidence does.
