---
name: board-init
description: Install the gated aluminum factory board system (governance engine, six stage gates, five specialist subagents, board workflows, domain skills, guard hook, Microsoft 365 and Telegram draft connectors) into the current project. Use when the user wants to set up or upgrade an AI board of directors, stage gate governance, or the aluminum extrusion factory board in a repository.
argument-hint: "[--name-en \"Project name\"] [--name-ar \"اسم المشروع\"]"
disable-model-invocation: true
allowed-tools: Bash(python3 *), Read
---

# Install the Board Governance Kit | تثبيت نظام مجلس الإدارة

The kit is copied INTO the project, not run from the plugin. The board's law (engine, rules, guard, agents,
constitution) must live in the project's own git history so every decision can be audited against the exact
rules that were in force.

## Steps

1. Show the plan first, writing nothing:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/init_board.py --target . --dry-run $ARGUMENTS
   ```
2. If it reports conflicts (existing `CLAUDE.md`, `.claude/settings.json`, `.mcp.json`...), stop and show them to
   the user. Only rerun with `--force` if the user explicitly agrees. Replaced files are backed up to
   `.board-backup/<timestamp>/`.
3. Install:
   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/init_board.py --target . $ARGUMENTS
   ```
4. Report the test result line and the gate status it prints.
5. Tell the user:
   - Restart Claude Code (or start a new session) so the new hooks, subagents and MCP servers load.
   - From now on the guard hook blocks agents from editing `state/`, `engine/`, `tests/`, `connectors/`,
     `.claude/`, `.mcp.json` and `CLAUDE.md`.
   - Board members enroll in their own terminal (the first one must be the chair):
     `python3 engine/board.py member-add --id chair01 --name-en "..." --name-ar "..." --roles chair`
   - Placeholder data is marked `[[UNVERIFIED]]` and blocks Gate G1 until replaced (see `DATA_INTAKE.md`).

## Upgrade an existing board

Upgrading replaces law and code, so it is human only. Never run it yourself. Give the user this command for
their own terminal (it keeps all board data: events, members, journal, constraints, rules, documents):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/init_board.py --target . --upgrade
```

## What gets installed

| Path | Purpose |
|---|---|
| `CLAUDE.md` | Board_Exec constitution: Iron Laws, operating loop, subject IDs, skills, connectors |
| `engine/board.py` | Deterministic gate engine: hash chained events, PIN approvals, payments, reconciliation |
| `state/` | Rules (6 gates), Syrian constraints (90 day expiry), empty event log, journal, members |
| `.claude/agents/` | tech-spec-auditor, legal-counsel, fin-acct-controller, ops-logistics-coord, hr-planner |
| `.claude/commands/` | /board-review, /audit-contract, /verify-shipment, /gate-status, /authorize, /pay |
| `.claude/skills/` | 9 domain skills, 3 with calculators (press sizing, CPM, depreciation) |
| `.claude/hooks/`, `.claude/settings.json` | Guard hook and session start integrity check |
| `connectors/`, `.mcp.json` | board-ledger (read only), telegram-board and m365-drafts (drafts only) |
| `tests/` | 26 tests: G1 to G6 lifecycle, tamper, quorum, payments, connectors, guard |
| `demo/index.html` | Interactive simulator of the agents (example data) |
