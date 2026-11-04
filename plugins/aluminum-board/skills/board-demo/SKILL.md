---
name: board-demo
description: Launch the interactive Extrusion Board Room simulator, a React page that shows how Board_Exec routes work to five isolated agents, how verdicts bind to evidence, how the engine gates actions, and where human board members vote. Seven scenarios with example data. Use when the user wants to see, present, or explain how the board agents work.
argument-hint: "[--port 8000] [--copy demo/]"
allowed-tools: Bash(python3 *)
---

# Board Room Simulator | محاكاة غرفة مجلس الإدارة

## Serve it

Run in the background, because it keeps serving until stopped:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/serve_demo.py $ARGUMENTS
```

Read the real port from the first output line (it moves to the next free port if 8000 is taken). If a tool for
reporting a preview port is available, report that port. Then tell the user the address.

To put the page into the project instead (for GitHub Pages or a Codespaces port):

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/serve_demo.py --copy demo/
```

## What the viewer will see

| Scenario | Shows |
|---|---|
| G1 vendor quote | Press sizing passes, technical veto on an unserviceable PLC |
| G2 contract | Legal veto, new draft makes verdicts stale, re-review, the viewer casts the board vote |
| G3 early pour | Engine refuses the pour, CPM shows waiting costs zero schedule days |
| G4 shipment shortage | Reconciliation, payment freeze, claim deadline, rule gap |
| G4 expert travel | Travel lock, idle cost, options for the board |
| Tamper | Hash chain catches an edited event, engine refuses writes, human restores |
| Milestone payment | Dual key, viewer votes, single use authorization |

Say plainly that it is a scripted simulation with example data: no agents, connectors or messages are called.
The browser needs internet access for React and fonts.
