"""
Outbound policy shared by every write capable connector (Telegram outbox, Outlook drafts, OneDrive drafts).

Board rule: agents create DRAFTS only. A human sends.
Additional rule (CLAUDE.md Iron Law 3): a draft of type `instruction` (RFP release, payment order,
booking request, pour order, signing pack) must cite an engine event that AUTHORIZED a matching action.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("BOARD_ROOT", Path(__file__).resolve().parent.parent))  # data root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))  # code always from this checkout
import board as engine  # noqa: E402

KINDS = {
    "status_update": "Progress or gate status. No commitment to a third party.",
    "gate_alert": "A block, veto, tamper or stale verdict that humans must see.",
    "meeting_notice": "Board meeting logistics and agenda.",
    "instruction": "Anything that commits money, people, contracts or site work. Needs auth_seq.",
}


class PolicyError(Exception):
    pass


def check_kind(kind: str, auth_seq, action_hint: str | None = None) -> dict | None:
    """Validate a draft kind. For instructions, return the ACTION_AUTHORIZED event it rests on."""
    if kind not in KINDS:
        raise PolicyError(f"kind must be one of {sorted(KINDS)}")
    if kind != "instruction":
        return None
    if auth_seq in (None, ""):
        raise PolicyError("An instruction draft needs auth_seq: run `python3 engine/board.py authorize <action>` first "
                          "and cite the ALLOW event number.")
    board = engine.Board(ROOT)
    evs = board.events()
    problems = board.verify_chain(evs)
    if problems:
        raise PolicyError("Event chain broken. No instruction drafts until `verify` is clean.")
    try:
        seq = int(auth_seq)
    except (TypeError, ValueError):
        raise PolicyError("auth_seq must be an integer event number")
    if not 1 <= seq <= len(evs):
        raise PolicyError(f"auth_seq {seq} does not exist")
    ev = evs[seq - 1]
    if ev["type"] != "ACTION_AUTHORIZED":
        raise PolicyError(f"event {seq} is {ev['type']}, not ACTION_AUTHORIZED")
    if action_hint and ev["payload"]["action"] != action_hint:
        raise PolicyError(f"event {seq} authorized `{ev['payload']['action']}`, not `{action_hint}`")
    return ev


def footer(kind: str, ev: dict | None) -> str:
    base = f"[board:{kind}]"
    if ev:
        base += f" [auth seq {ev['seq']} {ev['payload']['action']} ref={ev['payload'].get('ref')} hash {ev['hash'][:12]}]"
    return base
