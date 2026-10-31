#!/usr/bin/env python3
"""
PreToolUse guard. Defense in depth for the governance engine.

Blocks (exit 2) when an agent tries to:
  1. Edit or Write protected files (state/, engine/, tests/, .claude/, CLAUDE.md).
  2. Run human only engine commands (approve, attest, member-add, resolve-discrepancy, register-shipment).
  3. Touch protected paths from Bash with anything other than read only tools or the engine itself.

Humans who must change the rules launch Claude Code with BOARD_MAINTENANCE=1.
An agent cannot set that variable for the hook process from inside its own shell.
"""
import json
import os
import re
import shlex
import sys

PROTECTED = ("state/", "engine/", "tests/", ".claude/", "CLAUDE.md")
HUMAN_ONLY = ("approve", "attest", "member-add", "resolve-discrepancy", "register-shipment")
AGENT_ENGINE_CMDS = {"status", "check-gate", "advance", "authorize", "record-verdict", "reconcile",
                     "journal-add", "verify", "members", "rules", "-h", "--help"}
READ_ONLY = {"cat", "head", "tail", "less", "grep", "rg", "ls", "wc", "jq", "sha256sum", "diff", "file",
             "stat", "find", "column", "sort", "uniq", "cut", "echo", "true"}
GIT_READ = {"log", "diff", "status", "show", "blame", "rev-parse"}


def block(msg: str) -> None:
    print(f"BLOCKED by governance guard: {msg}", file=sys.stderr)
    sys.exit(2)


def project_rel(path: str, root: str) -> str:
    p = os.path.normpath(os.path.join(root, path)) if not os.path.isabs(path) else os.path.normpath(path)
    try:
        return os.path.relpath(p, root)
    except ValueError:
        return p


def is_protected(rel: str) -> bool:
    rel = rel.replace("\\", "/")
    return any(rel == p.rstrip("/") or rel.startswith(p) for p in PROTECTED)


def check_bash(cmd: str) -> None:
    if re.search(r"board\.py\b[^;&|\n]*\b(" + "|".join(HUMAN_ONLY) + r")\b", cmd):
        block("this engine command is HUMAN ONLY. A board member runs it in their own terminal with their PIN.")
    mentions = any(p.rstrip("/") in cmd for p in PROTECTED)
    if not mentions:
        return
    if re.search(r"(>>?|\btee\b)\s*\S*(" + "|".join(re.escape(p.rstrip('/')) for p in PROTECTED) + r")", cmd):
        block("redirecting output into protected governance files is not allowed.")
    for seg in re.split(r"\|\||&&|[;|\n]", cmd):
        seg = seg.strip()
        if not seg:
            continue
        try:
            toks = shlex.split(seg)
        except ValueError:
            block("could not parse a command that touches protected files.")
        while toks and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", toks[0]):
            toks.pop(0)
        if not toks:
            continue
        head = os.path.basename(toks[0])
        # Whole command mentions a protected path, so every segment must be harmless.
        # This closes `cd state && rm *` style bypasses.
        if head == "cd":
            continue
        if head in READ_ONLY and not any(t in ("-i", "--in-place", "-delete", "-exec") for t in toks):
            continue
        if head == "git" and len(toks) > 1 and toks[1] in GIT_READ:
            continue
        if head in ("python", "python3") and len(toks) > 2 and toks[1].endswith("engine/board.py") \
                and toks[2] in AGENT_ENGINE_CMDS:
            continue
        if head in ("python", "python3") and toks[1:3] == ["-m", "unittest"]:
            continue
        block(f"`{head}` may not touch protected governance paths. Use `python3 engine/board.py ...` "
              f"for state changes, or ask a human to edit with BOARD_MAINTENANCE=1.")


def main() -> None:
    if os.environ.get("BOARD_MAINTENANCE") == "1":
        sys.exit(0)
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    tool = data.get("tool_name", "")
    tin = data.get("tool_input", {}) or {}
    root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = tin.get("file_path") or tin.get("notebook_path") or ""
        if path and is_protected(project_rel(path, root)):
            block(f"{project_rel(path, root)} is governed state or law. State changes go through "
                  f"`python3 engine/board.py`. Rule changes need a human with BOARD_MAINTENANCE=1.")
    elif tool == "Bash":
        check_bash(tin.get("command", ""))
    sys.exit(0)


if __name__ == "__main__":
    main()
