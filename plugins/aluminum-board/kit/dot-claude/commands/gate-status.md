---
description: Where the project stands, what blocks the current gate, and exactly who must act next.
allowed-tools: Read, Bash(python3 engine/board.py:*)
---

1. Run `python3 engine/board.py verify`. If it reports TAMPER, stop everything and report it first.
2. Run `python3 engine/board.py status --json`.
3. Reply in Arabic first, then English:
   - Current gate and percentage of its conditions met.
   - Each unmet condition grouped by owner: **Agents** (verdicts to produce, with the subject IDs), **Humans**
     (attestations and approvals, with role and exact command), **Data** (UNVERIFIED files to replace).
   - Stale verdicts that must be re-run.
   - Controlled actions now ALLOWED and those LOCKED that people may be tempted to do early
     (foundations, expert travel, payments).
   - The single next action with the highest leverage on the critical path.
