# aluminum-board · Claude Code plugin

Gated agentic board of directors for an aluminum extrusion factory project in Syria.
مجلس إدارة ذكي ببوابات مراحل لمشروع مصنع بثق الألمنيوم.

## Install

```bash
/plugin marketplace add waleed178-del/board-members
```

```bash
/plugin install aluminum-board@board-members
```

To install from a branch before it is merged, add the marketplace with the branch after `#`:

```bash
/plugin marketplace add waleed178-del/board-members#waleed/eloquent-cray-1ueca3
```

## Skills in this plugin

| Skill | What it does |
|---|---|
| `/aluminum-board:board-init` | Installs the governance kit into the current project (asks before overwriting anything) |
| `/aluminum-board:board-demo` | Serves the interactive Board Room simulator |

After `board-init`, restart Claude Code. The project then has:

- `CLAUDE.md` constitution, `engine/board.py`, rules for 6 stage gates
- 5 subagents: tech-spec-auditor, legal-counsel, fin-acct-controller, ops-logistics-coord, hr-planner
- 6 workflows: `/board-review`, `/audit-contract`, `/verify-shipment`, `/gate-status`, `/authorize`, `/pay`
- 9 domain skills with press sizing, critical path and depreciation calculators
- Guard hook, board-ledger, telegram-board and m365-drafts connectors, 26 tests, the simulator

## Why the kit is copied into the project

The plugin installs nothing that runs globally: no hooks, no MCP servers. The board's law (engine, rules, guard,
agents, constitution) lives in each project's git history, so every decision can be audited against the exact
rules in force when it was made, and other projects on the same machine are not affected by the guard.

## Upgrade a board

Human only, in your own terminal (keeps events, members, journal, constraints, rules and documents):

```bash
python3 ~/.claude/plugins/cache/board-members/aluminum-board/*/skills/board-init/scripts/init_board.py --target . --upgrade
```

The exact path is printed by `/aluminum-board:board-init` and shown in `/plugin`.

## Rebuild the plugin from the repository

```bash
python3 tools/build_plugin.py
```

```bash
claude plugin validate plugins/aluminum-board
```
