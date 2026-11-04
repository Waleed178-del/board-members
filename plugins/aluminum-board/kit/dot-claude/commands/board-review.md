---
description: Full cross department board review of an event, proposal or document. Spawns subagents in parallel, records verdicts, checks the gate, writes a bilingual decision packet.
argument-hint: <file path or event description> [gate]
allowed-tools: Read, Grep, Glob, Write, Task, Bash(python3 engine/board.py:*)
---

Input: $ARGUMENTS

Follow CLAUDE.md section 3 exactly.

1. Run `python3 engine/board.py status --json`. Note `current_gate`, blockers, stale verdicts, open discrepancies.
2. Decide the gate and subject IDs (CLAUDE.md section 6) this input affects. If the input names a gate, use it.
   If it fits no subject, say so and stop: do not invent subjects.
3. Spawn the responsible subagents **in parallel in one message** with the `Task` tool. For each, pass:
   - `gate`, `subject`, the list of files to review (repo relative paths),
   - "Return exactly one JSON verdict per templates/verdict.schema.json. No prose outside the JSON."
   Agents: tech-spec-auditor, legal-counsel, fin-acct-controller, ops-logistics-coord, hr-planner, only those the
   RACI marks R or C for this gate.
4. For each verdict: write it to `verdicts/<YYYYMMDD-HHMM>_<agent>_<gate>_<subject>.json` and run
   `python3 engine/board.py record-verdict <file>`. If refused for format, fix format only and retry once.
5. Run `python3 engine/board.py check-gate <gate>`.
6. Write the decision packet to `packets/<YYYYMMDD>_<gate>_<subject>.md` using `templates/decision_packet.md`.
7. Reply with:
   - **الحقيقة الصعبة والفيتو النشط | Hard Truth and Active Vetoes**: who blocks and why, with finding codes.
   - **مخاطر المسارين | Cross Track Risk**: effect on Civil vs Equipment synchronization, in days and money.
   - **المطلوب من المجلس | Required Board Action**: exact human commands to run in their own terminal, for example
     `python3 engine/board.py approve rfp_lock --member <id> --decision APPROVE --evidence packets/<file>.md`
     and the negotiation leverage to use with the counterparty.
