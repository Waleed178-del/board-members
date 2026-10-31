#!/usr/bin/env python3
"""
HUMAN ONLY installer for staged governance changes.

    python3 staging/install.py

Copies every file under staging/ (except this installer and its README) to the same path in the repo root,
shows the plan first, requires typing INSTALL, then runs the full test suite. On test failure it restores
the previous files. Agents cannot run it: it needs an interactive terminal.
"""
import shutil
import subprocess
import sys
from pathlib import Path

STAGING = Path(__file__).resolve().parent
ROOT = STAGING.parent
SKIP = {"install.py", "README.md"}


def main() -> int:
    try:
        tty = open("/dev/tty", "r+", encoding="utf-8")
    except OSError:
        print("REFUSED: human only. No interactive terminal.", file=sys.stderr)
        return 2
    if not sys.stdin.isatty():
        print("REFUSED: human only. stdin is not a terminal.", file=sys.stderr)
        return 2
    files = [p for p in STAGING.rglob("*") if p.is_file() and p.relative_to(STAGING).as_posix() not in SKIP
             and "__pycache__" not in p.parts]
    plan = [(p, ROOT / p.relative_to(STAGING)) for p in sorted(files)]
    tty.write("Staged governance change. Files to install:\n")
    for src, dst in plan:
        tty.write(f"  {'UPDATE' if dst.exists() else 'NEW   '} {dst.relative_to(ROOT)}\n")
    tty.write("Type INSTALL to proceed: ")
    tty.flush()
    if tty.readline().strip() != "INSTALL":
        print("Cancelled.")
        return 0
    backup = {}
    for src, dst in plan:
        backup[dst] = dst.read_bytes() if dst.exists() else None
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    r = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"], cwd=ROOT)
    if r.returncode != 0:
        for dst, data in backup.items():
            if data is None:
                dst.unlink(missing_ok=True)
            else:
                dst.write_bytes(data)
        print("TESTS FAILED. Previous files restored. Nothing installed.", file=sys.stderr)
        return 3
    tty.write("Installed and tests pass. Remove staging/ now? [y/N]: ")
    tty.flush()
    if tty.readline().strip().lower() == "y":
        shutil.rmtree(STAGING)
    print("Done. Commit with: git add -A && git commit -m \"Install board skills and connectors\" && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main())
