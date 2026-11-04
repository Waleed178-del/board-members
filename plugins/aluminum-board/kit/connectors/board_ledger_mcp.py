#!/usr/bin/env python3
"""
board-ledger MCP server. READ ONLY window into the governance engine.

Lets any MCP client (Claude Code, Claude Desktop, Cowork) ask where the project stands without
shell access. It never writes events: authorize runs in dry run mode, status does not re-render files.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from mcp_stdio import ToolError, serve  # noqa: E402

ROOT = Path(os.environ.get("BOARD_ROOT", HERE.parent))  # data root
sys.path.insert(0, str(HERE.parent / "engine"))  # code always from this checkout
import board as engine  # noqa: E402

B = engine.Board(ROOT)
DIRS = {"packets": ROOT / "packets", "verdicts": ROOT / "verdicts", "reports": ROOT / "reports"}


def _guard(fn):
    def inner(args):
        try:
            return fn(args)
        except engine.GateError as e:
            raise ToolError(str(e))
    return inner


@_guard
def board_status(_args):
    return B.snapshot()


@_guard
def check_gate(args):
    gid = args.get("gate", "")
    st = B.fold()
    if gid in st["gates_passed"]:
        return {"gate": gid, "status": "PASSED", "at": st["gates_passed"][gid]["ts"]}
    missing = B.gate_missing(gid, st)
    return {"gate": gid, "status": "READY" if not missing else "BLOCKED", "missing": missing}


@_guard
def authorize_dry_run(args):
    ok, reasons, _ = B.authorize(args.get("action", ""), args.get("ref") or None, "mcp", dry_run=True)
    return {"action": args.get("action"), "ref": args.get("ref"), "would_allow": ok, "reasons": reasons,
            "note": "Dry run. Nothing logged. Real authorization must go through the engine CLI."}


@_guard
def verify_integrity(_args):
    problems = B.verify_chain(B.events()) + B.verify_journal() + B.verify_git_anchor()
    snap = B.snapshot()
    return {"ok": not problems, "problems": problems, "event_count": snap["event_count"],
            "chain_head": snap["chain_head"],
            "stale_verdicts": [k for k, v in snap["latest_verdicts"].items() if v["stale"]]}


def list_documents(args):
    kind = args.get("kind", "packets")
    if kind not in DIRS:
        raise ToolError(f"kind must be one of {sorted(DIRS)}")
    files = sorted((p for p in DIRS[kind].glob("*") if p.is_file() and not p.name.startswith(".")),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return [{"name": p.name, "bytes": p.stat().st_size} for p in files[: int(args.get("limit", 50))]]


def read_document(args):
    kind, name = args.get("kind", "packets"), args.get("name", "")
    if kind not in DIRS:
        raise ToolError(f"kind must be one of {sorted(DIRS)}")
    p = (DIRS[kind] / name).resolve()
    if p.parent != DIRS[kind].resolve() or not p.is_file():
        raise ToolError(f"{kind}/{name} not found")
    return p.read_text(encoding="utf-8")[:200_000]


TOOLS = {
    "board_status": ("Full project snapshot: gates with missing conditions, controlled actions, attestations, "
                     "open discrepancies, latest verdicts. Read only.",
                     {"type": "object", "properties": {}}, board_status),
    "check_gate": ("Unmet conditions for one gate (G1..G6).",
                   {"type": "object", "properties": {"gate": {"type": "string", "enum": ["G1", "G2", "G3", "G4", "G5", "G6"]}},
                    "required": ["gate"]}, check_gate),
    "authorize_dry_run": ("Would the engine allow this controlled action now? Does not log, does not authorize.",
                          {"type": "object", "properties": {"action": {"type": "string"}, "ref": {"type": "string"}},
                           "required": ["action"]}, authorize_dry_run),
    "verify_integrity": ("Verify the event hash chain, journal chain, git anchor and stale verdicts.",
                         {"type": "object", "properties": {}}, verify_integrity),
    "list_documents": ("List decision packets, verdicts or reconciliation reports, newest first.",
                       {"type": "object", "properties": {"kind": {"type": "string", "enum": sorted(DIRS)},
                                                         "limit": {"type": "integer"}}}, list_documents),
    "read_document": ("Read one packet, verdict or report by file name.",
                      {"type": "object", "properties": {"kind": {"type": "string", "enum": sorted(DIRS)},
                                                        "name": {"type": "string"}}, "required": ["kind", "name"]},
                      read_document),
}

if __name__ == "__main__":
    serve("board-ledger", "1.0.0", TOOLS,
          "Read only view of the aluminum factory board governance engine. Use board_status first.")
