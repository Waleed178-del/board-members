#!/usr/bin/env python3
"""
Board Governance Engine  |  محرك حوكمة مجلس الإدارة

Deterministic stage gate enforcer for the aluminum extrusion factory project.
Python standard library only. No network. No LLM calls.

Design rules
  1. State is an append only, hash chained event log (state/events.jsonl).
     state/project_ledger.json is a rendered snapshot. Editing it changes nothing.
  2. Gates, controlled actions, approvals and attestations are declared in
     state/raci_gates.json. The engine evaluates them. Agents cannot argue with it.
  3. Agent verdicts bind to the SHA256 of their evidence files. If a contract or
     spec changes after review, the verdict goes STALE and stops counting.
  4. Any evidence file that contains the token [[UNVERIFIED]] cannot support an
     APPROVED verdict, an approval or an attestation.
  5. Human only commands (approve, attest, member-add, resolve-discrepancy,
     register-shipment) require an interactive terminal and the member PIN.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import getpass
import hashlib
import hmac
import io
import json
import os
import secrets
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

GENESIS = "0" * 64
UNVERIFIED_TOKEN = "[[UNVERIFIED]]"
PBKDF2_ITERATIONS = 310_000
MIN_PIN_LENGTH = 8

AGENTS = {
    "tech-spec-auditor",
    "legal-counsel",
    "fin-acct-controller",
    "ops-logistics-coord",
    "hr-planner",
}
VERDICT_STATUSES = {"APPROVED", "VETOED", "NEEDS_INFO"}
SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
DATA_QUALITY = {"VERIFIED", "UNVERIFIED_INPUTS"}

JOURNAL_FIELDS = [
    "entry_id", "ts", "date", "entry_type", "classification", "account_dr",
    "account_cr", "amount", "currency", "fx_rate_to_usd", "amount_usd", "gate",
    "auth_seq", "ref", "memo", "prev_hash", "hash",
]
ENTRY_TYPES = {"PAYMENT", "ACCRUAL", "RECLASS", "DEPRECIATION", "ADJUSTMENT"}
CLASSIFICATIONS = {
    "PRE_OPERATING",      # مصاريف تأسيس
    "CAPEX_CWIP",         # أعمال رأسمالية قيد التنفيذ
    "CAPEX_FIXED_ASSET",  # أصول ثابتة
    "OPEX",               # مصاريف تشغيلية
    "DEPRECIATION",       # إهلاك
    "ADVANCE_TO_SUPPLIER",  # دفعات مقدمة للموردين
    "RETENTION_PAYABLE",  # محتجزات
    "GUARANTEE_MARGIN",   # تأمينات خطابات الضمان والاعتمادات
}


class GateError(Exception):
    """Raised when a request violates governance rules."""


# ----------------------------------------------------------------- utilities

def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def pin_hash(pin: str, salt_hex: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", pin.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    ).hex()


# ---------------------------------------------------------------- the board

class Board:
    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        self.state_dir = self.root / "state"
        self.events_path = self.state_dir / "events.jsonl"
        self.ledger_path = self.state_dir / "project_ledger.json"
        self.rules_path = self.state_dir / "raci_gates.json"
        self.members_path = self.state_dir / "board_members.json"
        self.journal_path = self.state_dir / "accounting_journal.csv"
        self.constraints_path = self.state_dir / "syrian_market_constraints.json"
        self._rules = None

    # ------------------------------------------------------------ loading
    @property
    def rules(self) -> dict:
        if self._rules is None:
            self._rules = json.loads(self.rules_path.read_text(encoding="utf-8"))
        return self._rules

    def events(self) -> list[dict]:
        if not self.events_path.exists():
            return []
        out = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
        return out

    def members(self) -> list[dict]:
        if not self.members_path.exists():
            return []
        return json.loads(self.members_path.read_text(encoding="utf-8")).get("members", [])

    def _save_members(self, members: list[dict]) -> None:
        doc = {
            "_doc": "Managed by engine/board.py member-add. PIN hashes are PBKDF2 SHA256. Do not edit by hand.",
            "members": members,
        }
        self.members_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # ------------------------------------------------------------ events
    def append_event(self, etype: str, payload: dict, actor: str) -> dict:
        evs = self.events()
        problems = self.verify_chain(evs)
        if problems:
            raise GateError("Event chain is broken. Refusing to write. Run `verify`. " + "; ".join(problems[:3]))
        ev = {
            "seq": len(evs) + 1,
            "ts": now_iso(),
            "type": etype,
            "actor": actor,
            "payload": payload,
            "prev_hash": evs[-1]["hash"] if evs else GENESIS,
        }
        ev["hash"] = sha256_text(canonical(ev))
        self.state_dir.mkdir(parents=True, exist_ok=True)
        with open(self.events_path, "a", encoding="utf-8") as fh:
            fh.write(canonical(ev) + "\n")
        self.render_ledger()
        return ev

    @staticmethod
    def verify_chain(evs: list[dict]) -> list[str]:
        problems = []
        prev = GENESIS
        for i, ev in enumerate(evs, start=1):
            body = {k: v for k, v in ev.items() if k != "hash"}
            if ev.get("seq") != i:
                problems.append(f"event {i}: sequence is {ev.get('seq')}, expected {i}")
            if ev.get("prev_hash") != prev:
                problems.append(f"event {i}: prev_hash does not link to event {i - 1}")
            if sha256_text(canonical(body)) != ev.get("hash"):
                problems.append(f"event {i}: content hash mismatch (tampered)")
            prev = ev.get("hash")
        return problems

    # ---------------------------------------------------------- evidence
    def _resolve(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if self.root not in p.parents and p != self.root:
            raise GateError(f"Evidence path escapes the project root: {rel}")
        return p

    def hash_evidence(self, paths: list[str], allow_unverified: bool = False) -> list[dict]:
        out = []
        for rel in paths or []:
            p = self._resolve(rel)
            if not p.is_file():
                raise GateError(f"Evidence file not found: {rel}")
            if not allow_unverified and self.file_unverified(p):
                raise GateError(f"Evidence {rel} still carries {UNVERIFIED_TOKEN}. Replace placeholder data first.")
            out.append({"path": str(p.relative_to(self.root)), "sha256": sha256_file(p)})
        return out

    @staticmethod
    def file_unverified(p: Path) -> bool:
        try:
            with open(p, "rb") as fh:
                return UNVERIFIED_TOKEN.encode() in fh.read()
        except OSError:
            return True

    def stale_evidence(self, evidence: list[dict]) -> list[str]:
        stale = []
        for item in evidence or []:
            p = self.root / item["path"]
            if not p.is_file():
                stale.append(f"{item['path']} (missing)")
            elif sha256_file(p) != item["sha256"]:
                stale.append(f"{item['path']} (changed since review)")
            elif self.file_unverified(p):
                stale.append(f"{item['path']} (now marked UNVERIFIED)")
        return stale

    # -------------------------------------------------------------- fold
    def fold(self) -> dict:
        st = {
            "gates_passed": {}, "flags": {}, "verdicts": {}, "approvals": {},
            "metrics": {}, "discrepancies": {}, "shipments": {}, "actions": [],
        }
        for ev in self.events():
            t, p = ev["type"], ev["payload"]
            meta = {"seq": ev["seq"], "ts": ev["ts"]}
            if t == "GATE_PASSED":
                st["gates_passed"][p["gate"]] = meta
            elif t == "VERDICT":
                st["verdicts"][f"{p['agent']}|{p['gate']}|{p['subject']}"] = {**p, **meta}
            elif t == "APPROVAL":
                st["approvals"].setdefault(p["key"], {})[p["member"]] = {**p, **meta}
            elif t == "ATTESTATION":
                st["flags"][p["flag"]] = {**p, **meta}
            elif t == "SHIPMENT_REGISTERED":
                st["shipments"][p["shipment"]] = {**p, **meta}
            elif t == "RECONCILIATION":
                st["metrics"][f"receipt_pct:{p['shipment']}"] = p["critical_receipt_pct"]
                for d in p["discrepancies"]:
                    st["discrepancies"][d["id"]] = {**d, "status": "OPEN", **meta}
                for item_id in p.get("cleared", []):
                    if item_id in st["discrepancies"] and st["discrepancies"][item_id]["status"] == "OPEN":
                        st["discrepancies"][item_id]["status"] = "CLEARED_BY_RECOUNT"
            elif t == "DISCREPANCY_RESOLVED":
                if p["id"] in st["discrepancies"]:
                    st["discrepancies"][p["id"]]["status"] = "RESOLVED"
                    st["discrepancies"][p["id"]]["resolution"] = p
            elif t in ("ACTION_AUTHORIZED", "ACTION_DENIED"):
                st["actions"].append({"type": t, **p, **meta})
        return st

    # -------------------------------------------------------- conditions
    def member_by_id(self, mid: str) -> dict | None:
        for m in self.members():
            if m["id"] == mid and m.get("active", True):
                return m
        return None

    def check(self, cond: dict, st: dict, ref: str | None = None) -> list[str]:
        """Return a list of unmet reasons. Empty list means the condition holds."""
        def sub(s: str) -> str:
            if "{ref}" in s:
                if not ref:
                    raise GateError("This action needs --ref (for example an invoice or milestone ID).")
                return s.replace("{ref}", ref)
            return s

        if "all" in cond:
            return [r for c in cond["all"] for r in self.check(c, st, ref)]
        if "any" in cond:
            results = [self.check(c, st, ref) for c in cond["any"]]
            return [] if any(not r for r in results) else ["none of: " + " | ".join("; ".join(r) for r in results)]

        if "gate_passed" in cond:
            g = cond["gate_passed"]
            return [] if g in st["gates_passed"] else [f"gate {g} not passed"]

        if "flag" in cond:
            name = cond["flag"]
            want = cond.get("equals", True)
            f = st["flags"].get(name)
            if not f:
                return [f"attestation `{name}` missing (human must run: attest {name})"]
            if f["value"] != want:
                return [f"attestation `{name}` is {f['value']}, needs {want}"]
            stale = self.stale_evidence(f.get("evidence", []))
            return [f"attestation `{name}` evidence stale: {', '.join(stale)}"] if stale else []

        if "verdict" in cond:
            agent, gate, subject = cond["verdict"], cond["gate"], sub(cond["subject"])
            v = st["verdicts"].get(f"{agent}|{gate}|{subject}")
            label = f"verdict {agent}/{gate}/{subject}"
            if not v:
                return [f"{label} missing"]
            if v["status"] != "APPROVED":
                return [f"{label} is {v['status']}"]
            if v["data_quality"] != "VERIFIED":
                return [f"{label} rests on UNVERIFIED inputs"]
            stale = self.stale_evidence(v.get("evidence", []))
            return [f"{label} is STALE: {', '.join(stale)}"] if stale else []

        if "approval" in cond:
            key = sub(cond["approval"])
            return self.check_approval(key, st)

        if "computed" in cond:
            fn = getattr(self, "computed_" + cond["computed"], None)
            if fn is None:
                raise GateError(f"Unknown computed condition: {cond['computed']}")
            return fn(st)

        raise GateError(f"Unknown condition shape: {cond}")

    def check_approval(self, key: str, st: dict) -> list[str]:
        base = key.split(":", 1)[0]
        spec = self.rules["approvals"].get(base)
        if spec is None:
            raise GateError(f"Approval key `{base}` is not defined in raci_gates.json")
        votes = st["approvals"].get(key, {})
        reasons = []
        approvers, approver_roles = [], set()
        for mid, vote in votes.items():
            m = self.member_by_id(mid)
            if not m:
                continue
            eligible = set(m["roles"]) & set(spec["roles"])
            if not eligible:
                continue
            if vote["decision"] == "REJECT":
                reasons.append(f"approval `{key}` REJECTED by {mid}: {vote.get('note', '')}".strip())
                continue
            stale = self.stale_evidence(vote.get("evidence", []))
            if stale:
                reasons.append(f"approval `{key}` by {mid} is STALE: {', '.join(stale)}")
                continue
            approvers.append(mid)
            approver_roles |= eligible
        if len(approvers) < spec["quorum"]:
            reasons.append(f"approval `{key}` has {len(approvers)}/{spec['quorum']} eligible APPROVE votes")
        missing_roles = [r for r in spec.get("required_roles", []) if r not in approver_roles]
        if missing_roles:
            reasons.append(f"approval `{key}` still needs role(s): {', '.join(missing_roles)}")
        return reasons

    # computed predicates ------------------------------------------------
    def computed_constraints_verified(self, st: dict) -> list[str]:
        if not self.constraints_path.exists():
            return ["state/syrian_market_constraints.json missing"]
        doc = json.loads(self.constraints_path.read_text(encoding="utf-8"))
        max_age = int(doc.get("max_age_days", 90))
        today = dt.date.today()
        reasons = []
        for name, sec in doc.get("sections", {}).items():
            if not sec.get("critical"):
                continue
            if not sec.get("verified"):
                reasons.append(f"constraints section `{name}` is UNVERIFIED")
                continue
            if not sec.get("verified_by"):
                reasons.append(f"constraints section `{name}` has no verified_by")
            try:
                age = (today - dt.date.fromisoformat(sec.get("verified_on") or "")).days
                if age > max_age:
                    reasons.append(f"constraints section `{name}` verified {age} days ago (limit {max_age})")
            except ValueError:
                reasons.append(f"constraints section `{name}` has no valid verified_on date")
        return reasons

    def computed_zero_open_discrepancies(self, st: dict) -> list[str]:
        open_ = [d for d, v in st["discrepancies"].items() if v["status"] == "OPEN"]
        return [f"{len(open_)} open shipment discrepancies: {', '.join(open_[:5])}"] if open_ else []

    def computed_all_critical_received(self, st: dict) -> list[str]:
        if not st["shipments"]:
            return ["no expected shipments registered (human must run: register-shipment)"]
        reasons = []
        for sid in st["shipments"]:
            pct = st["metrics"].get(f"receipt_pct:{sid}")
            if pct is None:
                reasons.append(f"shipment {sid} not reconciled")
            elif pct < 100:
                reasons.append(f"shipment {sid} critical receipt {pct}% (needs 100%)")
        return reasons

    # -------------------------------------------------------------- gates
    def gate_order(self) -> list[str]:
        return [g["id"] for g in self.rules["gates"]]

    def gate(self, gid: str) -> dict:
        for g in self.rules["gates"]:
            if g["id"] == gid:
                return g
        raise GateError(f"Unknown gate {gid}. Valid: {', '.join(self.gate_order())}")

    def gate_missing(self, gid: str, st: dict | None = None) -> list[str]:
        st = st or self.fold()
        g = self.gate(gid)
        order = self.gate_order()
        idx = order.index(gid)
        reasons = []
        if idx > 0 and order[idx - 1] not in st["gates_passed"]:
            reasons.append(f"previous gate {order[idx - 1]} not passed")
        for c in g["conditions"]:
            reasons.extend(self.check(c, st))
        return reasons

    def current_gate(self, st: dict) -> str | None:
        for gid in self.gate_order():
            if gid not in st["gates_passed"]:
                return gid
        return None

    def advance(self, gid: str, actor: str) -> dict:
        st = self.fold()
        if gid in st["gates_passed"]:
            raise GateError(f"Gate {gid} already passed at {st['gates_passed'][gid]['ts']}")
        missing = self.gate_missing(gid, st)
        if missing:
            raise GateError(f"Gate {gid} BLOCKED:\n  - " + "\n  - ".join(missing))
        return self.append_event("GATE_PASSED", {"gate": gid}, actor)

    # ------------------------------------------------------------ actions
    def authorize(self, action: str, ref: str | None, actor: str, dry_run: bool = False) -> tuple[bool, list[str], dict | None]:
        spec = self.rules["controlled_actions"].get(action)
        if spec is None:
            raise GateError(f"Unknown controlled action `{action}`. Valid: {', '.join(self.rules['controlled_actions'])}")
        st = self.fold()
        reasons = [r for c in spec["conditions"] for r in self.check(c, st, ref)]
        ok = not reasons
        ev = None
        if not dry_run:
            ev = self.append_event(
                "ACTION_AUTHORIZED" if ok else "ACTION_DENIED",
                {"action": action, "ref": ref, "payment": bool(spec.get("payment")), "reasons": reasons},
                actor,
            )
        return ok, reasons, ev

    # ------------------------------------------------------------ verdicts
    def record_verdict(self, verdict: dict, actor: str) -> dict:
        required = ["agent", "gate", "subject", "status", "data_quality", "summary_en", "summary_ar", "findings", "evidence"]
        missing = [k for k in required if k not in verdict]
        if missing:
            raise GateError(f"Verdict missing fields: {', '.join(missing)}")
        if verdict["agent"] not in AGENTS:
            raise GateError(f"Unknown agent `{verdict['agent']}`")
        valid_gates = set(self.gate_order()) | {"OPS"}
        if verdict["gate"] not in valid_gates:
            raise GateError(f"Verdict gate must be one of {sorted(valid_gates)}")
        if verdict["status"] not in VERDICT_STATUSES:
            raise GateError(f"Verdict status must be one of {sorted(VERDICT_STATUSES)}")
        if verdict["data_quality"] not in DATA_QUALITY:
            raise GateError(f"data_quality must be one of {sorted(DATA_QUALITY)}")
        for f in verdict["findings"]:
            if f.get("severity") not in SEVERITIES:
                raise GateError(f"Finding severity must be one of {sorted(SEVERITIES)}: {f}")
        if verdict["status"] == "APPROVED":
            crit = [f for f in verdict["findings"] if f["severity"] == "CRITICAL"]
            if crit:
                raise GateError("Inconsistent verdict: APPROVED with CRITICAL findings. Agent must VETO or resolve.")
            if not verdict["evidence"]:
                raise GateError("APPROVED verdict must cite at least one evidence file.")
        unverified = [e for e in verdict["evidence"] if self.file_unverified(self._resolve(e))] if verdict["evidence"] else []
        if unverified:
            verdict["data_quality"] = "UNVERIFIED_INPUTS"
        payload = {
            "agent": verdict["agent"],
            "gate": verdict["gate"],
            "subject": verdict["subject"],
            "status": verdict["status"],
            "data_quality": verdict["data_quality"],
            "summary_en": verdict["summary_en"],
            "summary_ar": verdict["summary_ar"],
            "findings": verdict["findings"],
            "conditions": verdict.get("conditions", []),
            "evidence": self.hash_evidence(verdict["evidence"], allow_unverified=True),
            "unverified_evidence": unverified,
        }
        return self.append_event("VERDICT", payload, actor)

    # ------------------------------------------------------- human actions
    def authenticate(self, member_id: str, pin: str) -> dict:
        m = self.member_by_id(member_id)
        if not m:
            raise GateError(f"Unknown or inactive member `{member_id}`")
        if not hmac.compare_digest(pin_hash(pin, m["salt"]), m["pin_hash"]):
            raise GateError("PIN rejected")
        return m

    def add_member(self, mid: str, name_en: str, name_ar: str, roles: list[str], pin: str,
                   sponsor_id: str | None = None, sponsor_pin: str | None = None) -> dict:
        valid_roles = set(self.rules["roles"])
        bad = [r for r in roles if r not in valid_roles]
        if bad:
            raise GateError(f"Unknown roles {bad}. Valid: {sorted(valid_roles)}")
        if len(pin) < MIN_PIN_LENGTH:
            raise GateError(f"PIN must be at least {MIN_PIN_LENGTH} characters")
        members = self.members()
        if any(m["id"] == mid for m in members):
            raise GateError(f"Member `{mid}` exists")
        if members:
            if not sponsor_id:
                raise GateError("An existing chair must sponsor new members (--sponsor)")
            sponsor = self.authenticate(sponsor_id, sponsor_pin or "")
            if "chair" not in sponsor["roles"]:
                raise GateError("Sponsor must hold the chair role")
        elif "chair" not in roles:
            raise GateError("The first member must hold the chair role")
        salt = secrets.token_hex(16)
        members.append({
            "id": mid, "name_en": name_en, "name_ar": name_ar, "roles": roles,
            "salt": salt, "pin_hash": pin_hash(pin, salt), "active": True, "added": now_iso(),
        })
        self._save_members(members)
        return self.append_event("MEMBER_ADDED", {"member": mid, "roles": roles, "sponsor": sponsor_id}, mid)

    def approve(self, key: str, member_id: str, pin: str, decision: str, evidence: list[str], note: str) -> dict:
        m = self.authenticate(member_id, pin)
        base = key.split(":", 1)[0]
        spec = self.rules["approvals"].get(base)
        if spec is None:
            raise GateError(f"Approval key `{base}` not defined. Valid: {', '.join(self.rules['approvals'])}")
        if not set(m["roles"]) & set(spec["roles"]):
            raise GateError(f"Member {member_id} roles {m['roles']} are not eligible for `{base}` ({spec['roles']})")
        if decision not in ("APPROVE", "REJECT"):
            raise GateError("decision must be APPROVE or REJECT")
        if decision == "APPROVE" and not evidence:
            raise GateError("APPROVE requires evidence files (the decision packet at minimum)")
        payload = {
            "key": key, "member": member_id, "roles": m["roles"], "decision": decision,
            "note": note, "evidence": self.hash_evidence(evidence, allow_unverified=(decision == "REJECT")),
        }
        return self.append_event("APPROVAL", payload, member_id)

    def attest(self, flag: str, member_id: str, pin: str, value: bool, evidence: list[str], note: str) -> dict:
        m = self.authenticate(member_id, pin)
        spec = self.rules["attestations"].get(flag)
        if spec is None:
            raise GateError(f"Attestation `{flag}` not defined. Valid: {', '.join(self.rules['attestations'])}")
        if not set(m["roles"]) & set(spec["roles"]):
            raise GateError(f"Member {member_id} roles {m['roles']} cannot attest `{flag}` ({spec['roles']})")
        if value and spec.get("evidence_required", True) and not evidence:
            raise GateError(f"Attesting `{flag}` = true requires evidence files")
        payload = {"flag": flag, "member": member_id, "value": value, "note": note,
                   "evidence": self.hash_evidence(evidence)}
        return self.append_event("ATTESTATION", payload, member_id)

    def register_shipment(self, shipment: str, member_id: str, pin: str, description: str) -> dict:
        m = self.authenticate(member_id, pin)
        if not set(m["roles"]) & {"operations_director", "chair"}:
            raise GateError("Only operations_director or chair can register expected shipments")
        return self.append_event("SHIPMENT_REGISTERED", {"shipment": shipment, "description": description}, member_id)

    def resolve_discrepancy(self, did: str, member_id: str, pin: str, evidence: list[str], note: str) -> dict:
        m = self.authenticate(member_id, pin)
        if not set(m["roles"]) & {"operations_director", "legal_advisor", "chair"}:
            raise GateError("Only operations_director, legal_advisor or chair can resolve discrepancies")
        st = self.fold()
        d = st["discrepancies"].get(did)
        if not d or d["status"] != "OPEN":
            raise GateError(f"No OPEN discrepancy `{did}`")
        if not evidence:
            raise GateError("Resolution requires evidence (claim settlement, credit note, replacement receipt)")
        return self.append_event("DISCREPANCY_RESOLVED",
                                 {"id": did, "member": member_id, "note": note, "evidence": self.hash_evidence(evidence)},
                                 member_id)

    # -------------------------------------------------------- reconciliation
    @staticmethod
    def _read_qty_csv(path: Path) -> dict[str, dict]:
        rows = {}
        with open(path, newline="", encoding="utf-8-sig") as fh:
            reader = csv.DictReader(fh)
            need = {"item_code", "qty"}
            if not need <= set(reader.fieldnames or []):
                raise GateError(f"{path.name} must have columns item_code, qty (optional: description, critical)")
            for r in reader:
                code = (r.get("item_code") or "").strip()
                if not code:
                    continue
                try:
                    qty = Decimal((r.get("qty") or "0").strip())
                except InvalidOperation:
                    raise GateError(f"{path.name}: bad qty for {code}")
                if code in rows:
                    rows[code]["qty"] += qty
                else:
                    rows[code] = {
                        "qty": qty,
                        "description": (r.get("description") or "").strip(),
                        "critical": (r.get("critical") or "").strip().upper() in ("Y", "YES", "TRUE", "1"),
                    }
        return rows

    def reconcile(self, shipment: str, packing: str, invoice: str, received: str, actor: str) -> tuple[dict, str]:
        st = self.fold()
        if shipment not in st["shipments"]:
            raise GateError(f"Shipment `{shipment}` not registered. A human must run register-shipment first.")
        pk = self._read_qty_csv(self._resolve(packing))
        iv = self._read_qty_csv(self._resolve(invoice))
        rc = self._read_qty_csv(self._resolve(received))
        codes = sorted(set(pk) | set(iv) | set(rc))
        discrepancies, lines = [], []
        crit_expected = crit_received = Decimal(0)
        for c in codes:
            p, i, r = (pk.get(c, {}).get("qty"), iv.get(c, {}).get("qty"), rc.get(c, {}).get("qty"))
            critical = pk.get(c, {}).get("critical", False) or iv.get(c, {}).get("critical", False)
            desc = (pk.get(c) or iv.get(c) or rc.get(c))["description"]
            if critical and p is not None:
                crit_expected += p
                crit_received += min(r or Decimal(0), p)
            problem = []
            if p is None:
                problem.append("not on packing list")
            if i is None:
                problem.append("not on commercial invoice")
            if r is None:
                problem.append("not physically received")
            if p is not None and i is not None and p != i:
                problem.append(f"packing {p} vs invoice {i}")
            if p is not None and r is not None and r != p:
                problem.append(f"received {r} vs packing {p}")
            status = "OK" if not problem else ("CRITICAL" if critical else "MISMATCH")
            lines.append((c, desc, p, i, r, "Y" if critical else "", status, "; ".join(problem)))
            if problem:
                discrepancies.append({"id": f"{shipment}:{c}", "item_code": c, "critical": critical,
                                      "detail": "; ".join(problem)})
        pct = float(round(crit_received / crit_expected * 100, 2)) if crit_expected else 0.0
        open_ids = {d for d, v in st["discrepancies"].items() if v["status"] == "OPEN" and d.startswith(shipment + ":")}
        new_ids = {d["id"] for d in discrepancies}
        cleared = sorted(open_ids - new_ids)
        evidence = self.hash_evidence([packing, invoice, received], allow_unverified=True)
        ev = self.append_event("RECONCILIATION", {
            "shipment": shipment, "critical_receipt_pct": pct,
            "discrepancies": [d for d in discrepancies if d["id"] not in open_ids],
            "still_open": sorted(new_ids & open_ids), "cleared": cleared, "evidence": evidence,
        }, actor)
        # report
        out = io.StringIO()
        out.write(f"# Shipment Reconciliation | مطابقة الشحنة: {shipment}\n\n")
        out.write(f"Event seq {ev['seq']} at {ev['ts']}\n\n")
        out.write(f"Critical receipt | نسبة استلام المكونات الحرجة: **{pct}%**\n\n")
        out.write(f"Discrepancies | الفروقات: **{len(discrepancies)}** "
                  f"(critical: {sum(1 for d in discrepancies if d['critical'])})\n\n")
        if discrepancies:
            out.write("> Payment freeze: milestone payments are blocked until every discrepancy is resolved "
                      "by a human with evidence. Legal must issue a claim notice within the contract notice period.\n"
                      "> تجميد الدفعات: لا تُصرف دفعات المراحل حتى تُغلق كل الفروقات بدليل موثق.\n\n")
        out.write("| item_code | description | packing | invoice | received | critical | status | detail |\n")
        out.write("|---|---|---|---|---|---|---|---|\n")
        for row in lines:
            out.write("| " + " | ".join("" if x is None else str(x) for x in row) + " |\n")
        report_dir = self.root / "reports"
        report_dir.mkdir(exist_ok=True)
        report_path = report_dir / f"reconciliation_{shipment}_seq{ev['seq']}.md"
        report_path.write_text(out.getvalue(), encoding="utf-8")
        return ev, str(report_path.relative_to(self.root))

    # -------------------------------------------------------------- journal
    def journal_rows(self) -> list[dict]:
        if not self.journal_path.exists():
            return []
        with open(self.journal_path, newline="", encoding="utf-8") as fh:
            return list(csv.DictReader(fh))

    def verify_journal(self) -> list[str]:
        problems, prev = [], GENESIS
        for i, row in enumerate(self.journal_rows(), start=1):
            body = {k: row[k] for k in JOURNAL_FIELDS if k != "hash"}
            if row["prev_hash"] != prev:
                problems.append(f"journal row {i}: prev_hash does not link")
            if sha256_text(canonical(body)) != row["hash"]:
                problems.append(f"journal row {i}: content hash mismatch (tampered)")
            prev = row["hash"]
        return problems

    def journal_add(self, *, date: str, entry_type: str, classification: str, account_dr: str,
                    account_cr: str, amount: str, currency: str, fx_rate_to_usd: str, gate: str,
                    ref: str, memo: str, auth_seq: int | None, actor: str) -> dict:
        if entry_type not in ENTRY_TYPES:
            raise GateError(f"entry_type must be one of {sorted(ENTRY_TYPES)}")
        if classification not in CLASSIFICATIONS:
            raise GateError(f"classification must be one of {sorted(CLASSIFICATIONS)}")
        try:
            dt.date.fromisoformat(date)
            amt = Decimal(amount)
            fx = Decimal(fx_rate_to_usd)
        except (ValueError, InvalidOperation):
            raise GateError("date must be YYYY-MM-DD, amount and fx_rate_to_usd must be numbers")
        if amt <= 0 or fx <= 0:
            raise GateError("amount and fx_rate_to_usd must be positive")
        if gate not in set(self.gate_order()) | {"OPS"}:
            raise GateError("gate must be G1..G6 or OPS")
        if entry_type == "PAYMENT":
            if auth_seq is None:
                raise GateError("PAYMENT entries need --auth-seq pointing to an ACTION_AUTHORIZED payment event (dual key rule)")
            evs = self.events()
            if not (1 <= auth_seq <= len(evs)):
                raise GateError(f"auth_seq {auth_seq} does not exist")
            ev = evs[auth_seq - 1]
            if ev["type"] != "ACTION_AUTHORIZED" or not ev["payload"].get("payment"):
                raise GateError(f"Event {auth_seq} is not an authorized payment action")
            used = {r["auth_seq"] for r in self.journal_rows() if r["entry_type"] == "PAYMENT"}
            if str(auth_seq) in used:
                raise GateError(f"Authorization {auth_seq} already consumed by a PAYMENT entry")
        problems = self.verify_journal()
        if problems:
            raise GateError("Journal chain broken. Refusing to write: " + "; ".join(problems[:3]))
        rows = self.journal_rows()
        row = {
            "entry_id": f"J{len(rows) + 1:05d}", "ts": now_iso(), "date": date, "entry_type": entry_type,
            "classification": classification, "account_dr": account_dr, "account_cr": account_cr,
            "amount": str(amt), "currency": currency.upper(), "fx_rate_to_usd": str(fx),
            "amount_usd": str((amt * fx).quantize(Decimal("0.01"))), "gate": gate,
            "auth_seq": "" if auth_seq is None else str(auth_seq), "ref": ref, "memo": memo,
            "prev_hash": rows[-1]["hash"] if rows else GENESIS,
        }
        row["hash"] = sha256_text(canonical(row))
        new_file = not self.journal_path.exists() or self.journal_path.stat().st_size == 0
        with open(self.journal_path, "a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=JOURNAL_FIELDS)
            if new_file:
                w.writeheader()
            w.writerow(row)
        self.append_event("JOURNAL_ENTRY", {"entry_id": row["entry_id"], "hash": row["hash"],
                                            "classification": classification, "amount_usd": row["amount_usd"]}, actor)
        return row

    def verify_git_anchor(self) -> list[str]:
        """The committed copy of the event log and journal must be a prefix of the working copy.
        Detects deletion or rewrite of history that a local hash chain alone cannot detect."""
        import subprocess
        problems = []
        for path in (self.events_path, self.journal_path):
            rel = path.relative_to(self.root).as_posix()
            try:
                r = subprocess.run(["git", "-C", str(self.root), "show", f"HEAD:{rel}"],
                                   capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired):
                return ["git not available: history anchor unchecked"]
            if r.returncode != 0:
                continue  # not committed yet
            committed = r.stdout
            current = path.read_bytes() if path.exists() else b""
            if not current.startswith(committed):
                problems.append(f"{rel}: working copy does not extend the committed history (rewrite or deletion)")
        return problems

    # --------------------------------------------------------------- ledger
    def snapshot(self) -> dict:
        st = self.fold()
        gates = []
        for g in self.rules["gates"]:
            gid = g["id"]
            passed = st["gates_passed"].get(gid)
            missing = [] if passed else self.gate_missing(gid, st)
            gates.append({
                "id": gid, "name_en": g["name_en"], "name_ar": g["name_ar"],
                "status": "PASSED" if passed else ("READY" if not missing else "BLOCKED"),
                "passed_at": passed["ts"] if passed else None, "missing": missing,
            })
        actions = {}
        for name, spec in self.rules["controlled_actions"].items():
            needs_ref = "{ref}" in json.dumps(spec["conditions"])
            if needs_ref:
                actions[name] = "PER_REFERENCE"
                continue
            reasons = [r for c in spec["conditions"] for r in self.check(c, st)]
            actions[name] = "ALLOWED" if not reasons else "LOCKED"
        evs = self.events()
        return {
            "_generated": "DO NOT EDIT. Rendered from state/events.jsonl by engine/board.py.",
            "project": self.rules.get("project", {}),
            "rendered_at": now_iso(),
            "event_count": len(evs),
            "chain_head": evs[-1]["hash"] if evs else GENESIS,
            "current_gate": self.current_gate(st),
            "gates": gates,
            "controlled_actions": actions,
            "open_discrepancies": {k: v for k, v in st["discrepancies"].items() if v["status"] == "OPEN"},
            "attestations": {k: {"value": v["value"], "by": v["member"], "ts": v["ts"]} for k, v in st["flags"].items()},
            "latest_verdicts": {k: {"status": v["status"], "data_quality": v["data_quality"], "ts": v["ts"],
                                    "stale": bool(self.stale_evidence(v["evidence"]))} for k, v in st["verdicts"].items()},
        }

    def render_ledger(self) -> dict:
        snap = self.snapshot()
        self.ledger_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return snap


# ------------------------------------------------------------------- CLI

def _ask_secret(prompt: str) -> str:
    """Read a secret from the controlling terminal only. Agents have none."""
    try:
        with open("/dev/tty", "r"):
            pass
    except OSError:
        raise GateError("This command is HUMAN ONLY. It needs an interactive terminal (no /dev/tty found). "
                        "Run it yourself in a separate terminal, not through an agent.")
    if not sys.stdin.isatty():
        raise GateError("This command is HUMAN ONLY. stdin is not a terminal (piped input refused).")
    return getpass.getpass(prompt)


def _print_snapshot(snap: dict, brief: bool) -> None:
    proj = snap["project"]
    print(f"== {proj.get('name_en', 'Project')} | {proj.get('name_ar', '')}")
    print(f"   events={snap['event_count']}  chain_head={snap['chain_head'][:12]}  current_gate={snap['current_gate']}")
    for g in snap["gates"]:
        mark = {"PASSED": "[x]", "READY": "[>]", "BLOCKED": "[ ]"}[g["status"]]
        print(f"{mark} {g['id']} {g['name_en']} | {g['name_ar']}  -> {g['status']}")
        if g["status"] != "PASSED" and (not brief or g["id"] == snap["current_gate"]):
            for m in g["missing"]:
                print(f"      - {m}")
    locked = [a for a, s in snap["controlled_actions"].items() if s == "LOCKED"]
    allowed = [a for a, s in snap["controlled_actions"].items() if s == "ALLOWED"]
    print(f"   actions ALLOWED: {', '.join(allowed) or 'none'}")
    if not brief:
        print(f"   actions LOCKED:  {', '.join(locked) or 'none'}")
    if snap["open_discrepancies"]:
        print(f"   OPEN DISCREPANCIES (payments frozen): {', '.join(snap['open_discrepancies'])}")


def main(argv: list[str] | None = None) -> int:
    root = Path(os.environ.get("BOARD_ROOT", Path(__file__).resolve().parent.parent))
    board = Board(root)
    ap = argparse.ArgumentParser(prog="board.py", description="Board governance engine | محرك الحوكمة")
    sp = ap.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("status", help="Show gates, blockers, actions")
    s.add_argument("--json", action="store_true")
    s.add_argument("--brief", action="store_true")

    s = sp.add_parser("check-gate", help="List unmet conditions for a gate")
    s.add_argument("gate")

    s = sp.add_parser("advance", help="Pass a gate if every condition holds")
    s.add_argument("gate")
    s.add_argument("--actor", default="board_exec")

    s = sp.add_parser("authorize", help="Request authorization for a controlled action (logged)")
    s.add_argument("action")
    s.add_argument("--ref")
    s.add_argument("--actor", default="board_exec")
    s.add_argument("--dry-run", action="store_true", help="Evaluate only, write nothing")

    s = sp.add_parser("record-verdict", help="Record a subagent verdict JSON file")
    s.add_argument("file")
    s.add_argument("--actor", default="board_exec")

    s = sp.add_parser("reconcile", help="Diff packing list vs invoice vs physical receipt")
    s.add_argument("--shipment", required=True)
    s.add_argument("--packing", required=True)
    s.add_argument("--invoice", required=True)
    s.add_argument("--received", required=True)
    s.add_argument("--actor", default="warehouse")

    s = sp.add_parser("journal-add", help="Append an accounting journal entry")
    for a in ("date", "entry-type", "classification", "account-dr", "account-cr", "amount", "currency", "gate", "ref"):
        s.add_argument(f"--{a}", required=True)
    s.add_argument("--fx-rate-to-usd", default="1")
    s.add_argument("--memo", default="")
    s.add_argument("--auth-seq", type=int)
    s.add_argument("--actor", default="fin_acct")

    sp.add_parser("verify", help="Verify event chain, journal chain, and evidence freshness")
    sp.add_parser("members", help="List board members")
    sp.add_parser("rules", help="Print approval keys, attestations and controlled actions")

    # human only
    s = sp.add_parser("member-add", help="[HUMAN] Enroll a board member")
    s.add_argument("--id", required=True)
    s.add_argument("--name-en", required=True)
    s.add_argument("--name-ar", required=True)
    s.add_argument("--roles", required=True, help="comma separated")
    s.add_argument("--sponsor", help="existing chair id (required after the first member)")

    s = sp.add_parser("approve", help="[HUMAN] Vote on an approval key")
    s.add_argument("key")
    s.add_argument("--member", required=True)
    s.add_argument("--decision", choices=["APPROVE", "REJECT"], required=True)
    s.add_argument("--evidence", nargs="*", default=[])
    s.add_argument("--note", default="")

    s = sp.add_parser("attest", help="[HUMAN] Attest a physical or legal fact")
    s.add_argument("flag")
    s.add_argument("--member", required=True)
    s.add_argument("--value", choices=["true", "false"], default="true")
    s.add_argument("--evidence", nargs="*", default=[])
    s.add_argument("--note", default="")

    s = sp.add_parser("register-shipment", help="[HUMAN] Declare an expected shipment")
    s.add_argument("shipment")
    s.add_argument("--member", required=True)
    s.add_argument("--description", default="")

    s = sp.add_parser("resolve-discrepancy", help="[HUMAN] Close a shipment discrepancy with evidence")
    s.add_argument("id")
    s.add_argument("--member", required=True)
    s.add_argument("--evidence", nargs="*", default=[])
    s.add_argument("--note", default="")

    args = ap.parse_args(argv)
    try:
        if args.cmd == "status":
            snap = board.render_ledger()
            if args.json:
                print(json.dumps(snap, ensure_ascii=False, indent=2))
            else:
                _print_snapshot(snap, args.brief)
        elif args.cmd == "check-gate":
            missing = board.gate_missing(args.gate)
            g = board.gate(args.gate)
            if args.gate in board.fold()["gates_passed"]:
                print(f"{args.gate} already PASSED")
            elif missing:
                print(f"{args.gate} {g['name_en']} | {g['name_ar']}: BLOCKED")
                for m in missing:
                    print(f"  - {m}")
                return 3
            else:
                print(f"{args.gate}: READY. Run: python3 engine/board.py advance {args.gate}")
        elif args.cmd == "advance":
            ev = board.advance(args.gate, args.actor)
            print(f"GATE {args.gate} PASSED (event {ev['seq']}, hash {ev['hash'][:12]})")
        elif args.cmd == "authorize":
            ok, reasons, ev = board.authorize(args.action, args.ref, args.actor, args.dry_run)
            tag = f" (event {ev['seq']})" if ev else " (dry run, not logged)"
            if ok:
                print(f"ALLOW {args.action} ref={args.ref}{tag}")
            else:
                print(f"DENY {args.action} ref={args.ref}{tag}")
                for r in reasons:
                    print(f"  - {r}")
                return 3
        elif args.cmd == "record-verdict":
            verdict = json.loads(Path(args.file).read_text(encoding="utf-8"))
            ev = board.record_verdict(verdict, args.actor)
            p = ev["payload"]
            print(f"VERDICT recorded seq={ev['seq']} {p['agent']}/{p['gate']}/{p['subject']} = {p['status']} "
                  f"data_quality={p['data_quality']}")
            if p["unverified_evidence"]:
                print(f"  ! UNVERIFIED evidence: {', '.join(p['unverified_evidence'])}. This verdict will not open any gate.")
        elif args.cmd == "reconcile":
            ev, report = board.reconcile(args.shipment, args.packing, args.invoice, args.received, args.actor)
            p = ev["payload"]
            print(f"RECONCILED {args.shipment}: critical receipt {p['critical_receipt_pct']}%, "
                  f"new discrepancies {len(p['discrepancies'])}, still open {len(p['still_open'])}, "
                  f"cleared {len(p['cleared'])}. Report: {report}")
            if p["discrepancies"] or p["still_open"]:
                return 3
        elif args.cmd == "journal-add":
            row = board.journal_add(
                date=args.date, entry_type=args.entry_type, classification=args.classification,
                account_dr=args.account_dr, account_cr=args.account_cr, amount=args.amount,
                currency=args.currency, fx_rate_to_usd=args.fx_rate_to_usd, gate=args.gate, ref=args.ref,
                memo=args.memo, auth_seq=args.auth_seq, actor=args.actor)
            print(f"JOURNAL {row['entry_id']} {row['classification']} {row['amount']} {row['currency']} "
                  f"(USD {row['amount_usd']}) hash {row['hash'][:12]}")
        elif args.cmd == "verify":
            problems = board.verify_chain(board.events()) + board.verify_journal() + board.verify_git_anchor()
            snap = board.snapshot()
            stale = [k for k, v in snap["latest_verdicts"].items() if v["stale"]]
            for p in problems:
                print(f"TAMPER: {p}")
            for k in stale:
                print(f"STALE VERDICT: {k}")
            if problems:
                return 4
            print(f"OK: {snap['event_count']} events and {len(board.journal_rows())} journal rows verified. "
                  f"{len(stale)} stale verdicts.")
        elif args.cmd == "members":
            for m in board.members():
                print(f"{m['id']}  {m['name_en']} | {m['name_ar']}  roles={','.join(m['roles'])}  active={m.get('active', True)}")
            if not board.members():
                print("No members enrolled. A human chair must run member-add first.")
        elif args.cmd == "rules":
            r = board.rules
            print("APPROVAL KEYS:")
            for k, v in r["approvals"].items():
                print(f"  {k}: quorum {v['quorum']}, roles {v['roles']}, required {v.get('required_roles', [])}")
            print("ATTESTATIONS:")
            for k, v in r["attestations"].items():
                print(f"  {k}: roles {v['roles']}")
            print("CONTROLLED ACTIONS:")
            for k, v in r["controlled_actions"].items():
                print(f"  {k}{' [payment]' if v.get('payment') else ''}: {v.get('label_en', '')}")
        elif args.cmd == "member-add":
            pin = _ask_secret(f"New PIN for {args.id} (min {MIN_PIN_LENGTH} chars): ")
            if pin != _ask_secret("Repeat PIN: "):
                raise GateError("PINs do not match")
            sponsor_pin = _ask_secret(f"Sponsor {args.sponsor} PIN: ") if args.sponsor else None
            ev = board.add_member(args.id, args.name_en, args.name_ar,
                                  [r.strip() for r in args.roles.split(",") if r.strip()], pin,
                                  args.sponsor, sponsor_pin)
            print(f"MEMBER {args.id} enrolled (event {ev['seq']})")
        elif args.cmd == "approve":
            pin = _ask_secret(f"PIN for {args.member}: ")
            ev = board.approve(args.key, args.member, pin, args.decision, args.evidence, args.note)
            print(f"{args.decision} recorded for {args.key} by {args.member} (event {ev['seq']})")
        elif args.cmd == "attest":
            pin = _ask_secret(f"PIN for {args.member}: ")
            ev = board.attest(args.flag, args.member, pin, args.value == "true", args.evidence, args.note)
            print(f"ATTESTED {args.flag}={args.value} by {args.member} (event {ev['seq']})")
        elif args.cmd == "register-shipment":
            pin = _ask_secret(f"PIN for {args.member}: ")
            ev = board.register_shipment(args.shipment, args.member, pin, args.description)
            print(f"SHIPMENT {args.shipment} registered (event {ev['seq']})")
        elif args.cmd == "resolve-discrepancy":
            pin = _ask_secret(f"PIN for {args.member}: ")
            ev = board.resolve_discrepancy(args.id, args.member, pin, args.evidence, args.note)
            print(f"RESOLVED {args.id} (event {ev['seq']})")
    except GateError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
