#!/usr/bin/env python3
"""
PreToolUse guard. Defense in depth for the governance engine and the connectors.

Blocks (exit 2) when an agent tries to:
  1. Edit or Write protected files (state/, engine/, tests/, connectors/, .claude/, .mcp.json, CLAUDE.md).
  2. Run human only commands (engine approve/attest/member-add/resolve-discrepancy/register-shipment,
     connectors/telegram_send.py, connectors/m365_login.py, staging/install.py).
  3. Touch protected paths from Bash with anything other than read only tools, the engine, or skill calculators.
  4. Mention BOARD_MAINTENANCE in a shell command (the flag belongs to the human's launch environment).
  5. Call any MCP tool that is not provably read only or an approved drafts only tool.

Humans who must change the rules launch Claude Code with BOARD_MAINTENANCE=1.
"""
import json
import os
import re
import shlex
import sys

PROTECTED = ("state/", "engine/", "tests/", "connectors/", ".claude/", ".mcp.json", "CLAUDE.md")
HUMAN_ONLY = ("approve", "attest", "member-add", "resolve-discrepancy", "register-shipment")
HUMAN_ONLY_SCRIPTS = ("telegram_send.py", "m365_login.py", "install.py")
AGENT_ENGINE_CMDS = {"status", "check-gate", "advance", "authorize", "record-verdict", "reconcile",
                     "journal-add", "verify", "members", "rules", "-h", "--help"}
READ_ONLY = {"cat", "head", "tail", "less", "grep", "rg", "ls", "wc", "jq", "sha256sum", "diff", "file",
             "stat", "find", "column", "sort", "uniq", "cut", "echo", "true"}
GIT_READ = {"log", "diff", "status", "show", "blame", "rev-parse"}
SKILL_SCRIPT = re.compile(r"^(\$CLAUDE_PROJECT_DIR/|\./)?\.claude/skills/[a-z0-9-]+/scripts/[a-z0-9_]+\.py$")

# MCP policy: a tool passes if it is an approved drafts only tool, or if its name has a read verb and no write verb.
MCP_DRAFT_ALLOW = {"telegram_queue_draft", "outlook_create_draft", "calendar_create_hold", "onedrive_upload_draft"}
MCP_READ_ALLOW = {"board_status", "check_gate", "authorize_dry_run", "verify_integrity", "list_documents",
                  "read_document", "telegram_read_messages", "telegram_list_drafts"}
MCP_READ = {"search", "read", "list", "get", "fetch", "find", "describe", "show", "view", "status", "check",
            "verify", "availability", "dry", "resolve"}
MCP_WRITE = {"send", "reply", "forward", "share", "delete", "remove", "trash", "publish", "post", "invite",
             "permission", "permissions", "merge", "push", "archive", "move", "update", "create", "upload",
             "write", "execute", "deploy", "apply", "set", "add", "edit", "rename", "copy", "approve",
             "submit", "pay", "transfer", "sign", "cancel", "trigger", "fire", "run"}


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


def check_mcp(tool: str) -> None:
    name = tool.split("__")[-1]
    if name in MCP_DRAFT_ALLOW or name in MCP_READ_ALLOW:
        return
    tokens = set(re.split(r"[_\-]+", name.lower()))
    if tokens & MCP_WRITE:
        block(f"MCP tool `{name}` can change something outside this repo. Board rule: drafts only, humans send.")
    if not tokens & MCP_READ:
        block(f"MCP tool `{name}` is not recognised as read only. Add it to the guard allowlist with BOARD_MAINTENANCE=1 "
              f"after review.")


def check_bash(cmd: str) -> None:
    if "BOARD_MAINTENANCE" in cmd:
        block("BOARD_MAINTENANCE is set by a human when launching Claude Code, never inside a command.")
    if re.search(r"board\.py\b[^;&|\n]*\b(" + "|".join(HUMAN_ONLY) + r")\b", cmd):
        block("this engine command is HUMAN ONLY. A board member runs it in their own terminal with their PIN.")
    if any(s in cmd for s in HUMAN_ONLY_SCRIPTS):
        block("this script is HUMAN ONLY (sending, signing in, installing). Run it in your own terminal.")
    if not any(p.rstrip("/") in cmd for p in PROTECTED):
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
        if head == "cd":
            continue
        if head in READ_ONLY and not any(t in ("-i", "--in-place", "-delete", "-exec") for t in toks):
            continue
        if head == "git" and len(toks) > 1 and toks[1] in GIT_READ:
            continue
        if head in ("python", "python3") and len(toks) > 2 and toks[1].endswith("engine/board.py") \
                and toks[2] in AGENT_ENGINE_CMDS:
            continue
        if head in ("python", "python3") and len(toks) > 1 and SKILL_SCRIPT.match(toks[1]):
            continue  # print only calculators shipped with skills
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
        block("unreadable hook input")
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
    elif tool.startswith("mcp__"):
        check_mcp(tool)
    sys.exit(0)


if __name__ == "__main__":
    main()
