#!/usr/bin/env python3
"""
Assemble the installable Claude Code plugin `aluminum-board` from this repository.

    python3 tools/build_plugin.py

Output: plugins/aluminum-board/kit/  (the governance kit board-init copies into a project)
        plugins/aluminum-board/skills/board-demo/assets/index.html

The kit is the repository's current system with the staged update (skills, agents, guard,
constitution, connector tests) applied. Dot paths are stored as `dot-*` inside the kit so this
repository does not discover the kit's .claude/ folder as its own; board-init restores the dots.
"""
from __future__ import annotations

import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "aluminum-board"
KIT = PLUGIN / "kit"
STAGING = REPO / "staging"

# (source relative to repo, destination relative to kit). Later entries win.
FILES = [
    ("CLAUDE.md", "CLAUDE.md"),
    ("DATA_INTAKE.md", "DATA_INTAKE.md"),
    ("CONNECTORS.md", "CONNECTORS.md"),
    ("README.md", "BOARD_README.md"),
    (".mcp.json", "dot-mcp.json"),
    (".gitignore", "dot-gitignore"),
    ("engine/board.py", "engine/board.py"),
    ("state/raci_gates.json", "state/raci_gates.json"),
    ("state/syrian_market_constraints.json", "state/syrian_market_constraints.json"),
    ("templates/decision_packet.md", "templates/decision_packet.md"),
    ("templates/verdict.schema.json", "templates/verdict.schema.json"),
    ("contracts/clause_library.md", "contracts/clause_library.md"),
    ("specs/market_study.md", "specs/market_study.md"),
    ("specs/rfp_spec_v1.md", "specs/rfp_spec_v1.md"),
    ("specs/shipments/TEMPLATE_packing.csv", "specs/shipments/TEMPLATE_packing.csv"),
    ("tests/test_engine.py", "tests/test_engine.py"),
    ("demo/index.html", "demo/index.html"),
]
DIRS = [
    ("connectors", "connectors", "*.py"),
    (".claude/commands", "dot-claude/commands", "*.md"),
    (".claude/agents", "dot-claude/agents", "*.md"),
]
STAGED = [  # staging/<x> -> kit/<y>
    ("CLAUDE.md", "CLAUDE.md"),
    (".claude/settings.json", "dot-claude/settings.json"),
    (".claude/hooks/guard_state.py", "dot-claude/hooks/guard_state.py"),
    ("tests/test_connectors.py", "tests/test_connectors.py"),
]
EMPTY = {
    "state/events.jsonl": "",
    "state/board_members.json": '{\n  "_doc": "Managed by engine/board.py member-add. PIN hashes are PBKDF2 SHA256. Do not edit by hand.",\n  "members": []\n}\n',
    "state/accounting_journal.csv": "entry_id,ts,date,entry_type,classification,account_dr,account_cr,amount,currency,fx_rate_to_usd,amount_usd,gate,auth_seq,ref,memo,prev_hash,hash\n",
    "verdicts/.gitkeep": "", "packets/.gitkeep": "", "reports/.gitkeep": "", "outbox/telegram/.gitkeep": "",
}


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def strip_install_section(text: str) -> str:
    start = text.find("## Install the staged governance change first")
    end = text.find("## Connector map")
    return text[:start] + text[end:] if start != -1 and end != -1 else text


def main() -> None:
    if KIT.exists():
        shutil.rmtree(KIT)
    for src, dst in FILES:
        copy(REPO / src, KIT / dst)
    for src, dst, pat in DIRS:
        for f in sorted((REPO / src).glob(pat)):
            copy(f, KIT / dst / f.name)
    for f in sorted((STAGING / ".claude" / "agents").glob("*.md")):  # staged agents preload skills
        copy(f, KIT / "dot-claude" / "agents" / f.name)
    for skill in sorted((STAGING / ".claude" / "skills").iterdir()):
        for f in skill.rglob("*"):
            if f.is_file() and "__pycache__" not in f.parts:
                copy(f, KIT / "dot-claude" / "skills" / skill.name / f.relative_to(skill))
    for src, dst in STAGED:
        copy(STAGING / src, KIT / dst)
    for rel, content in EMPTY.items():
        p = KIT / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
    c = KIT / "CONNECTORS.md"
    c.write_text(strip_install_section(c.read_text(encoding="utf-8")), encoding="utf-8")
    demo = PLUGIN / "skills" / "board-demo" / "assets" / "index.html"
    copy(REPO / "demo" / "index.html", demo)
    n = sum(1 for p in KIT.rglob("*") if p.is_file())
    print(f"kit: {n} files -> {KIT.relative_to(REPO)}")


if __name__ == "__main__":
    main()
