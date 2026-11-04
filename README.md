# Board Members | مجلس الإدارة الذكي

A gated, auditable agentic board for the Aluminum Extrusion Factory Project in Syria.
Claude Code orchestrates five specialist subagents. A deterministic Python engine decides what is allowed.
Humans approve with a PIN in their own terminal.

> It is a decision support, audit and workflow gating engine. It does not pour concrete, sign contracts or
> move money. It makes sure nobody does those things out of sequence or without evidence.

## Install as a Claude Code plugin | التثبيت كإضافة

```bash
/plugin marketplace add waleed178-del/board-members
```

```bash
/plugin install aluminum-board@board-members
```

Then, inside the project that should host the board, run `/aluminum-board:board-init` and restart Claude Code.
`/aluminum-board:board-demo` serves the simulator. Details: `plugins/aluminum-board/README.md`.

## Architecture | البنية

```
            Human board members (PIN, own terminal)
                 │ approve / attest / register-shipment / resolve-discrepancy
                 ▼
┌──────────────────────────────────────────────────────────────────┐
│ engine/board.py   deterministic gate engine (stdlib Python)       │
│   state/raci_gates.json         law: 6 gates, approvals, actions  │
│   state/events.jsonl            append only, SHA256 hash chain    │
│   state/accounting_journal.csv  append only, hash chain           │
│   state/project_ledger.json     rendered snapshot (read only)     │
│   state/syrian_market_constraints.json  local reality, 90 day TTL │
└──────────────────────────────────────────────────────────────────┘
                 ▲ status / check-gate / authorize / record-verdict / reconcile / journal-add
                 │
    Claude Code main session = Board_Exec (CLAUDE.md)
                 │ Task tool, parallel, isolated, read only
   ┌─────────────┼──────────────┬──────────────────┬─────────────┐
   ▼             ▼              ▼                  ▼             ▼
tech-spec    legal-counsel  fin-acct-controller ops-logistics  hr-planner
auditor                                         coord
(Sales +     (Legal)        (Finance +          (Civil +       (HR)
Production +                 Accounting)         Logistics +
Maintenance)                                     Warehouse)

Guard hook (.claude/hooks/guard_state.py) blocks agents from editing state, engine, rules,
or running human-only commands.
```

## The six gates | البوابات الست

| Gate | Name | Opens | Human keys |
|---|---|---|---|
| G1 | Spec and localization lock · تثبيت المواصفات والتوطين | RFP release | `rfp_lock` (2, technical director) |
| G2 | Contract and financial instrument · تثبيت العقد والأداة المالية | recruitment, freight quotes | `contract_signing` (3, chair + legal), `lc_issuance` (2, chair + finance) |
| G3 | Structural handshake · التسليم الإنشائي | foundation pouring | `civil_contract_award` (2, operations) |
| G4 | Port to warehouse + civil readiness · الجاهزية | **expert travel** | `civil_readiness_signoff` (2, operations + technical) |
| G5 | Installation and embedded training · التركيب والتدريب | | `installation_acceptance` (2, technical) |
| G6 | Commissioning and trial production · التشغيل التجريبي | retention release, capitalization | `final_acceptance` (3, chair + technical + finance) |

Milestone payments at any time after G2 need: zero open shipment discrepancies, a legal verdict, a finance verdict,
`payment_release:<ref>` quorum, an engine authorization, and a journal entry that consumes that authorization once.

## Integrity model | نموذج النزاهة

| Control | Stops | Limit |
|---|---|---|
| Evidence hashing | A contract or spec changed after review. The verdict goes STALE automatically | None within the repo |
| `[[UNVERIFIED]]` token | Decisions on placeholder data | A human must be honest when removing it |
| PIN + interactive terminal | Agents approving or attesting | A weak PIN can be brute forced offline. Use 12+ characters |
| Guard hook | Agents editing state, rules, engine | Pattern based. Determined obfuscation can evade it. It is a seatbelt, not a vault |
| Hash chain + git anchor (`verify`) | Silent edits or deletion of history | Only as strong as how often you commit and push |

## Quick start | البدء السريع

Requirements: Python 3.10+, git, Claude Code.

1. Run the tests.

```bash
python3 -m unittest discover -s tests -v
```

2. The chair enrolls themselves in their own terminal (not through Claude).

```bash
python3 engine/board.py member-add --id chair01 --name-en "Full Name" --name-ar "الاسم الكامل" --roles chair
```

3. The chair sponsors every other member.

```bash
python3 engine/board.py member-add --id fin01 --name-en "Name" --name-ar "الاسم" --roles finance_director --sponsor chair01
```

4. Replace placeholder data. See `DATA_INTAKE.md`.

5. Open Claude Code in this folder and run a review.

```bash
claude
```

Inside Claude Code: `/gate-status`, then `/board-review specs/rfp_spec_v1.md G1`.

6. Commit and push after every board session. This anchors the hash chain.

```bash
git add state packets verdicts reports && git commit -m "Board session YYYY-MM-DD" && git push
```

## Slash commands | الأوامر

| Command | Purpose |
|---|---|
| `/gate-status` | Current gate, blockers by owner, next highest leverage action |
| `/board-review <file or event> [gate]` | Parallel subagent review, verdicts recorded, bilingual packet |
| `/audit-contract <file> <gate> <subject>` | Clause matrix, redlines, payment and guarantee map |
| `/verify-shipment <id>` | Packing list vs invoice vs receipt. Freezes payments on mismatch |
| `/authorize <action> [ref]` | Engine check before drafting any outbound instruction |
| `/pay <ref> <file>` | Full dual key milestone payment workflow |

## Human only commands | أوامر الأعضاء فقط

| Command | Use |
|---|---|
| `approve <key> --member <id> --decision APPROVE\|REJECT --evidence <files>` | Vote. A single REJECT from an eligible member blocks until they change their vote |
| `attest <flag> --member <id> --evidence <files>` | Certify a physical or legal fact (contract signed, substation energized) |
| `register-shipment <id> --member <id>` | Declare an expected shipment so 100% receipt is measurable |
| `resolve-discrepancy <shipment:item> --member <id> --evidence <files>` | Close a shortage after settlement |

`python3 engine/board.py rules` lists every approval key, attestation and controlled action.

## Changing the rules | تعديل القواعد

`state/raci_gates.json`, `CLAUDE.md`, `.claude/` and `engine/` are protected from agents. To change them, a human
launches Claude Code with the maintenance flag, makes the change, runs the tests, and minutes the change:

```bash
BOARD_MAINTENANCE=1 claude
```

## Repository map

```
CLAUDE.md                     Board_Exec constitution
DATA_INTAKE.md                What to send, in priority order
engine/board.py               Gate engine and CLI
tests/test_engine.py          G1 to G6 lifecycle, tamper, stale, quorum, payment tests
state/                        Rules, constraints, event log, journal, members, snapshot
.claude/agents/               5 subagents (read only tools)
.claude/commands/             Slash commands
.claude/hooks/guard_state.py  Guard hook
.claude/settings.json         Hook wiring, SessionStart status
templates/                    Verdict schema, decision packet
contracts/clause_library.md   Mandatory clauses with minimums
specs/                        Market study, RFP, shipments
verdicts/ packets/ reports/   Generated outputs (commit them, they are the audit trail)
```
