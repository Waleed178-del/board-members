#!/usr/bin/env python3
"""
Install (or upgrade) the gated board governance kit into a project.

    python3 init_board.py --target . [--name-en "..."] [--name-ar "..."] [--dry-run] [--force]
    python3 init_board.py --target . --upgrade        # HUMAN ONLY: needs an interactive terminal

Fresh install
  Copies engine, rules, constitution, agents, workflows, skills, guard hook, connectors, templates,
  tests and the demo. Refuses to overwrite any existing file that differs unless --force, in which
  case the old file is backed up to .board-backup/<timestamp>/.

Upgrade
  Replaces code and law files with the plugin's version (backups kept). NEVER touches board data:
  state/events.jsonl, board_members.json, accounting_journal.csv, syrian_market_constraints.json,
  raci_gates.json, and anything in specs/, contracts/, packets/, verdicts/, reports/, outbox/.
"""
from __future__ import annotations

import argparse
import datetime as dt
import filecmp
import json
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parents[3] / "kit"

DATA_NEVER_OVERWRITE = {
    "state/events.jsonl", "state/board_members.json", "state/accounting_journal.csv",
    "state/syrian_market_constraints.json", "state/raci_gates.json",
}
DATA_PREFIXES = ("specs/", "contracts/", "packets/", "verdicts/", "reports/", "outbox/")


def dest_rel(kit_rel: str) -> str:
    return "/".join(("." + part[4:]) if part.startswith("dot-") else part for part in kit_rel.split("/"))


def is_data(rel: str) -> bool:
    return rel in DATA_NEVER_OVERWRITE or rel.startswith(DATA_PREFIXES)


def require_tty() -> None:
    try:
        open("/dev/tty").close()
    except OSError:
        sys.exit("REFUSED: --upgrade changes the board's law. A human runs it in their own terminal.")
    if not sys.stdin.isatty():
        sys.exit("REFUSED: --upgrade needs an interactive terminal.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Install the aluminum-board governance kit")
    ap.add_argument("--target", default=".")
    ap.add_argument("--name-en")
    ap.add_argument("--name-ar")
    ap.add_argument("--force", action="store_true", help="fresh install: overwrite differing files (backed up)")
    ap.add_argument("--upgrade", action="store_true", help="replace code and law, keep all board data")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    target = Path(a.target).resolve()
    if not KIT.is_dir():
        sys.exit(f"Kit not found at {KIT}. Reinstall the plugin.")
    existing_board = (target / "state" / "raci_gates.json").exists()
    if a.upgrade:
        if not existing_board:
            sys.exit("No board found in target (state/raci_gates.json missing). Run without --upgrade.")
        require_tty()
    elif existing_board and not a.force:
        sys.exit("A board already exists here. Use --upgrade (human, in a terminal) to update its code.")

    plan, conflicts = [], []
    for f in sorted(p for p in KIT.rglob("*") if p.is_file() and "__pycache__" not in p.parts):
        rel = dest_rel(f.relative_to(KIT).as_posix())
        dst = target / rel
        if not dst.exists():
            plan.append((f, dst, "NEW"))
        elif filecmp.cmp(f, dst, shallow=False):
            continue
        elif is_data(rel):
            continue  # board data is never overwritten
        elif a.upgrade or a.force:
            plan.append((f, dst, "REPLACE"))
        else:
            conflicts.append(rel)

    if conflicts:
        print("REFUSED: these files exist and differ. Nothing was written.")
        for c in conflicts:
            print(f"  {c}")
        print("Review them, then rerun with --force (old files are backed up to .board-backup/).")
        return 2

    for _, dst, kind in plan:
        print(f"  {kind:7} {dst.relative_to(target)}")
    print(f"{len(plan)} file(s) to write into {target}")
    if a.dry_run or not plan:
        return 0

    backup = target / ".board-backup" / dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for src, dst, kind in plan:
        if kind == "REPLACE":
            b = backup / dst.relative_to(target)
            b.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, b)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    rules = target / "state" / "raci_gates.json"
    if not a.upgrade and (a.name_en or a.name_ar):
        doc = json.loads(rules.read_text(encoding="utf-8"))
        if a.name_en:
            doc["project"]["name_en"] = a.name_en
        if a.name_ar:
            doc["project"]["name_ar"] = a.name_ar
        rules.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\nRunning the test suite in the target...")
    t = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=target,
                       capture_output=True, text=True)
    print((t.stderr.strip().splitlines() or ["(no output)"])[-1])
    subprocess.run([sys.executable, "engine/board.py", "status", "--brief"], cwd=target)
    if backup.exists():
        print(f"\nBackups of replaced files: {backup.relative_to(target)}")
    print("\nNext steps (human, own terminal):")
    print("  1. git add -A && git commit -m \"Install board governance kit\"")
    print("  2. python3 engine/board.py member-add --id chair01 --name-en \"...\" --name-ar \"...\" --roles chair")
    print("  3. Replace placeholder data, see DATA_INTAKE.md. Then in Claude Code: /gate-status")
    print("  4. Restart Claude Code so the new hooks, agents and MCP servers load.")
    return 0 if t.returncode == 0 else 3


if __name__ == "__main__":
    sys.exit(main())
