---
description: Ask the engine whether a controlled action is allowed. Run before drafting any outbound instruction.
argument-hint: <action> [ref]
allowed-tools: Bash(python3 engine/board.py:*)
---

Request: $ARGUMENTS

1. Run `python3 engine/board.py rules` if the action name is not exact, and map the request to one controlled action.
2. Run `python3 engine/board.py authorize <action> [--ref <ref>]`. This is logged in the audit chain.
3. On ALLOW: state the event sequence number. Only now may you draft the instruction, and it must cite that number.
4. On DENY: list each unmet condition, who owns it, and the command or verdict that clears it. Do not draft anything.
