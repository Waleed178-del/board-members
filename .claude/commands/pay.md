---
description: Milestone payment dual key workflow. Legal and finance verdicts, human quorum, engine authorization, journal entry.
argument-hint: <payment ref e.g. M2-VENDOR> <invoice or certificate file>
allowed-tools: Read, Grep, Glob, Write, Task, Bash(python3 engine/board.py:*)
---

Input: $ARGUMENTS

1. `python3 engine/board.py authorize release_milestone_payment --ref <ref> --dry-run` to see what is missing.
2. If verdicts are missing or stale, spawn in parallel:
   - `legal-counsel` gate `OPS` subject `payment:<ref>`: milestone event occurred, no blocking claims, guarantees valid.
   - `fin-acct-controller` gate `OPS` subject `payment:<ref>`: amount, retention, cash, FX, and the proposed journal entries.
   Record both through the engine.
3. Write `packets/<YYYYMMDD>_payment_<ref>.md`. Give the humans:
   `python3 engine/board.py approve payment_release:<ref> --member <id> --decision APPROVE --evidence packets/<file>.md <invoice>`
   (quorum 2, finance_director required).
4. Once approvals exist, run `python3 engine/board.py authorize release_milestone_payment --ref <ref>`.
   On ALLOW note the event `seq`.
5. After the human confirms the bank executed the transfer, post the journal entry:
   `python3 engine/board.py journal-add --date <YYYY-MM-DD> --entry-type PAYMENT --classification <...> --account-dr <...> --account-cr <...> --amount <...> --currency <...> --fx-rate-to-usd <...> --gate OPS --ref <ref> --auth-seq <seq> --memo "<...>"`
   One authorization pays once. The engine refuses reuse.
