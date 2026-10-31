---
description: Legal + Finance + Technical audit of a contract or amendment. Produces a clause matrix, redlines and a decision packet.
argument-hint: <contract file> <gate G2|G3|OPS> <subject e.g. equipment_contract | civil_contract>
allowed-tools: Read, Grep, Glob, Write, Task, Bash(python3 engine/board.py:*)
---

Input: $ARGUMENTS

1. `python3 engine/board.py status --brief`.
2. Confirm the file exists and read its first lines. If it carries `[[UNVERIFIED]]`, warn that verdicts will not count.
3. Spawn in parallel with `Task`:
   - `legal-counsel` on the given subject, with `contracts/clause_library.md` as the checklist.
   - `fin-acct-controller` on `payment_instrument` (equipment contract) or `civil_budget` (civil contract).
   - `tech-spec-auditor` on `contract_technical_annex` (equipment contract) or `foundation_blueprints` consistency (civil contract).
4. Record each verdict through the engine (CLAUDE.md section 3 step 4).
5. Write `packets/<YYYYMMDD>_<gate>_<subject>.md` from `templates/decision_packet.md`, including:
   - the full clause matrix from legal-counsel,
   - a single consolidated redline list in English for the counterparty, ordered CRITICAL first,
   - the payment schedule with guarantee coverage per milestone.
6. Reply with vetoes, the top 5 negotiation asks, and the human approval commands still required.
