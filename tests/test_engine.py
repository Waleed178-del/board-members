"""End to end tests for the governance engine. Run: python3 -m unittest discover -s tests -v"""
import datetime as dt
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "engine"))
import board as B  # noqa: E402

B.PBKDF2_ITERATIONS = 1_000  # fast tests; production keeps 310k

PIN = "correct-horse-1"


class Env:
    """Isolated project root with members, verified constraints and evidence files."""

    def __init__(self, verify_constraints=True):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "state").mkdir()
        shutil.copy(REPO / "state" / "raci_gates.json", self.dir / "state" / "raci_gates.json")
        cons = json.loads((REPO / "state" / "syrian_market_constraints.json").read_text(encoding="utf-8"))
        if verify_constraints:
            for sec in cons["sections"].values():
                sec.update(verified=True, verified_by="test", verified_on=dt.date.today().isoformat())
        (self.dir / "state" / "syrian_market_constraints.json").write_text(json.dumps(cons), encoding="utf-8")
        self.b = B.Board(self.dir)
        self.b.add_member("chair", "Chair", "الرئيس", ["chair"], PIN)
        for mid, roles in [
            ("fin", ["finance_director"]), ("tech", ["technical_director"]), ("ops", ["operations_director"]),
            ("legal", ["legal_advisor"]), ("hr", ["hr_director"]), ("bm", ["board_member"]),
        ]:
            self.b.add_member(mid, mid, mid, roles, PIN, "chair", PIN)

    def file(self, rel, text="evidence"):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return rel

    def verdict(self, agent, gate, subject, evidence, status="APPROVED", findings=None):
        return self.b.record_verdict({
            "agent": agent, "gate": gate, "subject": subject, "status": status, "data_quality": "VERIFIED",
            "summary_en": "ok", "summary_ar": "موافق", "findings": findings or [], "evidence": evidence,
        }, "test")

    def approve(self, key, members, evidence):
        for m in members:
            self.b.approve(key, m, PIN, "APPROVE", evidence, "")

    def attest(self, flag, member, evidence):
        self.b.attest(flag, member, PIN, True, evidence, "")

    def close(self):
        shutil.rmtree(self.dir)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.e = Env()
        self.b = self.e.b
        self.spec = self.e.file("specs/rfp_spec_v1.md", "press 2200 US ton")
        self.packet = self.e.file("packets/g1.md", "packet")

    def tearDown(self):
        self.e.close()

    def pass_g1(self):
        self.e.verdict("tech-spec-auditor", "G1", "rfp_spec", [self.spec])
        self.e.verdict("fin-acct-controller", "G1", "capex_budget", [self.spec])
        self.e.approve("rfp_lock", ["tech", "chair"], [self.packet])
        self.b.advance("G1", "test")

    # ------------------------------------------------------------ G1
    def test_g1_blocked_by_unverified_constraints(self):
        e = Env(verify_constraints=False)
        try:
            self.assertTrue(any("UNVERIFIED" in r for r in e.b.gate_missing("G1")))
        finally:
            e.close()

    def test_g1_passes_with_all_conditions(self):
        self.pass_g1()
        self.assertIn("G1", self.b.fold()["gates_passed"])

    def test_gates_cannot_skip(self):
        with self.assertRaises(B.GateError) as cm:
            self.b.advance("G2", "test")
        self.assertIn("previous gate G1 not passed", str(cm.exception))

    def test_quorum_and_required_role(self):
        self.e.verdict("tech-spec-auditor", "G1", "rfp_spec", [self.spec])
        self.e.verdict("fin-acct-controller", "G1", "capex_budget", [self.spec])
        self.e.approve("rfp_lock", ["chair", "bm"], [self.packet])
        missing = self.b.gate_missing("G1")
        self.assertTrue(any("technical_director" in r for r in missing))

    def test_reject_vetoes_approval(self):
        self.e.verdict("tech-spec-auditor", "G1", "rfp_spec", [self.spec])
        self.e.verdict("fin-acct-controller", "G1", "capex_budget", [self.spec])
        self.e.approve("rfp_lock", ["tech", "chair"], [self.packet])
        self.b.approve("rfp_lock", "bm", PIN, "REJECT", [], "tonnage too low")
        self.assertTrue(any("REJECTED" in r for r in self.b.gate_missing("G1")))

    # ------------------------------------------------------ evidence
    def test_verdict_goes_stale_when_evidence_changes(self):
        self.e.verdict("tech-spec-auditor", "G1", "rfp_spec", [self.spec])
        (self.e.dir / self.spec).write_text("press 1800 US ton", encoding="utf-8")
        self.assertTrue(any("STALE" in r for r in self.b.gate_missing("G1")))

    def test_unverified_evidence_cannot_open_gate(self):
        bad = self.e.file("specs/placeholder.md", "[[UNVERIFIED]] demo")
        ev = self.e.verdict("tech-spec-auditor", "G1", "rfp_spec", [bad])
        self.assertEqual(ev["payload"]["data_quality"], "UNVERIFIED_INPUTS")
        self.assertTrue(any("UNVERIFIED inputs" in r for r in self.b.gate_missing("G1")))

    def test_approved_with_critical_finding_rejected(self):
        with self.assertRaises(B.GateError):
            self.e.verdict("legal-counsel", "G2", "equipment_contract", [self.spec],
                           findings=[{"severity": "CRITICAL", "code": "NO_LD", "detail": "no penalty clause"}])

    def test_approval_needs_eligible_role_and_pin(self):
        with self.assertRaises(B.GateError):
            self.b.approve("lc_issuance", "tech", PIN, "APPROVE", [self.packet], "")
        with self.assertRaises(B.GateError):
            self.b.approve("rfp_lock", "tech", "wrong-pin-000", "APPROVE", [self.packet], "")

    # ------------------------------------------------------ actions
    def test_expert_travel_locked_until_g4(self):
        ok, reasons, ev = self.b.authorize("book_expert_travel", None, "test")
        self.assertFalse(ok)
        self.assertEqual(ev["type"], "ACTION_DENIED")

    def test_payment_journal_requires_authorization(self):
        with self.assertRaises(B.GateError):
            self.b.journal_add(date="2026-11-01", entry_type="PAYMENT", classification="ADVANCE_TO_SUPPLIER",
                               account_dr="1410", account_cr="1010", amount="100000", currency="USD",
                               fx_rate_to_usd="1", gate="G2", ref="ADV-1", memo="", auth_seq=None, actor="t")
        row = self.b.journal_add(date="2026-11-01", entry_type="ACCRUAL", classification="PRE_OPERATING",
                                 account_dr="1600", account_cr="2100", amount="2500", currency="USD",
                                 fx_rate_to_usd="1", gate="G1", ref="FEAS-1", memo="feasibility", auth_seq=None,
                                 actor="t")
        self.assertEqual(row["entry_id"], "J00001")
        self.assertEqual(self.b.verify_journal(), [])

    # ------------------------------------------------------ integrity
    def test_tamper_detected(self):
        self.pass_g1()
        lines = self.b.events_path.read_text(encoding="utf-8").splitlines()
        ev = json.loads(lines[-1])
        ev["payload"]["gate"] = "G6"
        lines[-1] = json.dumps(ev)
        self.b.events_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assertTrue(self.b.verify_chain(self.b.events()))
        with self.assertRaises(B.GateError):
            self.b.authorize("issue_rfp_to_vendors", None, "test")

    # ------------------------------------------------------ full lifecycle
    def test_full_lifecycle_g1_to_g6(self):
        e, b = self.e, self.b
        self.pass_g1()
        ok, _, _ = b.authorize("issue_rfp_to_vendors", None, "test")
        self.assertTrue(ok)

        # G2
        contract = e.file("contracts/equipment_contract.md", "LD 0.5%/week cap 10%, PB 10%")
        pkt2 = e.file("packets/g2.md")
        e.verdict("tech-spec-auditor", "G2", "contract_technical_annex", [contract])
        e.verdict("legal-counsel", "G2", "equipment_contract", [contract])
        e.verdict("fin-acct-controller", "G2", "payment_instrument", [contract])
        ok, reasons, _ = b.authorize("sign_equipment_contract", None, "test")
        self.assertFalse(ok)
        e.approve("contract_signing", ["chair", "legal", "tech"], [pkt2])
        ok, _, _ = b.authorize("sign_equipment_contract", None, "test")
        self.assertTrue(ok)
        signed = e.file("contracts/signed.pdf", "signed")
        e.attest("contract_signed", "legal", [signed])
        e.approve("lc_issuance", ["chair", "fin"], [pkt2])
        ok, _, auth = b.authorize("issue_lc_or_advance_payment", None, "test")
        self.assertTrue(ok)
        b.journal_add(date="2026-11-10", entry_type="PAYMENT", classification="ADVANCE_TO_SUPPLIER",
                      account_dr="1410", account_cr="1010", amount="300000", currency="EUR", fx_rate_to_usd="1.08",
                      gate="G2", ref="ADV-1", memo="30% advance", auth_seq=auth["seq"], actor="t")
        with self.assertRaises(B.GateError):  # same authorization cannot pay twice
            b.journal_add(date="2026-11-10", entry_type="PAYMENT", classification="ADVANCE_TO_SUPPLIER",
                          account_dr="1410", account_cr="1010", amount="300000", currency="EUR",
                          fx_rate_to_usd="1.08", gate="G2", ref="ADV-1", memo="dup", auth_seq=auth["seq"], actor="t")
        e.attest("advance_payment_made", "fin", [e.file("finance/swift.pdf", "mt103")])
        b.advance("G2", "test")

        # G3: foundations locked until blueprints
        self.assertFalse(b.authorize("pour_foundations", None, "test")[0])
        bp = e.file("specs/foundation_blueprints.pdf", "dwg")
        civ = e.file("contracts/civil_contract.md", "civil")
        e.attest("foundation_blueprints_received", "tech", [bp])
        e.verdict("tech-spec-auditor", "G3", "foundation_blueprints", [bp])
        e.verdict("legal-counsel", "G3", "civil_contract", [civ])
        e.verdict("fin-acct-controller", "G3", "civil_budget", [civ])
        e.verdict("ops-logistics-coord", "G3", "civil_and_logistics_plan", [civ])
        e.verdict("hr-planner", "G3", "staffing_plan", [e.file("hr/plan.md")])
        e.approve("civil_contract_award", ["ops", "chair"], [e.file("packets/g3.md")])
        b.advance("G3", "test")
        self.assertTrue(b.authorize("pour_foundations", None, "test")[0])

        # G4: shipment with a discrepancy freezes payments
        b.register_shipment("SH1", "ops", PIN, "press")
        hdr = "item_code,description,qty,critical\n"
        pk = e.file("specs/shipments/SH1_packing.csv", hdr + "P1,container,1,Y\nV1,valve,4,Y\nB1,bolts,100,N\n")
        iv = e.file("specs/shipments/SH1_invoice.csv", hdr + "P1,container,1,Y\nV1,valve,4,Y\nB1,bolts,100,N\n")
        rc = e.file("specs/shipments/SH1_received.csv", hdr + "P1,container,1,Y\nV1,valve,3,Y\nB1,bolts,100,N\n")
        ev, _ = b.reconcile("SH1", pk, iv, rc, "test")
        self.assertLess(ev["payload"]["critical_receipt_pct"], 100)
        e.verdict("legal-counsel", "OPS", "payment:M2", [civ])
        e.verdict("fin-acct-controller", "OPS", "payment:M2", [civ])
        e.approve("payment_release:M2", ["fin", "chair"], [e.file("packets/m2.md")])
        ok, reasons, _ = b.authorize("release_milestone_payment", "M2", "test")
        self.assertFalse(ok)
        self.assertTrue(any("discrepanc" in r for r in reasons))
        rc2 = e.file("specs/shipments/SH1_received_v2.csv", hdr + "P1,container,1,Y\nV1,valve,4,Y\nB1,bolts,100,N\n")
        ev2, _ = b.reconcile("SH1", pk, iv, rc2, "test")
        self.assertEqual(ev2["payload"]["critical_receipt_pct"], 100.0)
        self.assertIn("SH1:V1", ev2["payload"]["cleared"])
        self.assertTrue(b.authorize("release_milestone_payment", "M2", "test")[0])

        self.assertFalse(b.authorize("book_expert_travel", None, "test")[0])
        for flag in ("customs_cleared", "foundations_cured", "hangar_closed", "substation_energized"):
            e.attest(flag, "ops", [e.file(f"site/{flag}.pdf")])
        e.verdict("ops-logistics-coord", "G4", "installation_readiness", [e.file("site/readiness.md")])
        e.verdict("hr-planner", "G4", "technicians_onboarded", [e.file("hr/onboard.md")])
        e.approve("civil_readiness_signoff", ["ops", "tech"], [e.file("packets/g4.md")])
        b.advance("G4", "test")
        self.assertTrue(b.authorize("book_expert_travel", None, "test")[0])

        # G5
        for flag, m in (("experts_on_site", "hr"), ("installation_complete", "tech"),
                        ("spare_parts_handover_complete", "tech")):
            e.attest(flag, m, [e.file(f"site/{flag}.pdf")])
        e.verdict("tech-spec-auditor", "G5", "spare_parts_handover", [e.file("site/spares.md")])
        e.verdict("hr-planner", "G5", "shadowing_records", [e.file("hr/shadow.md")])
        e.approve("installation_acceptance", ["tech", "ops"], [e.file("packets/g5.md")])
        b.advance("G5", "test")

        # G6
        for flag in ("acceptance_tests_passed", "trial_production_complete"):
            e.attest(flag, "tech", [e.file(f"site/{flag}.pdf")])
        e.verdict("tech-spec-auditor", "G6", "acceptance_test_results", [e.file("site/fat.md")])
        e.verdict("legal-counsel", "G6", "performance_bond_release", [contract])
        e.verdict("fin-acct-controller", "G6", "retention_and_capitalization", [e.file("finance/cap.md")])
        e.approve("final_acceptance", ["chair", "tech", "fin"], [e.file("packets/g6.md")])
        b.advance("G6", "test")
        self.assertTrue(b.authorize("release_retention_payment", None, "test")[0])
        self.assertTrue(b.authorize("capitalize_assets", None, "test")[0])
        self.assertEqual(b.verify_chain(b.events()), [])
        snap = b.render_ledger()
        self.assertIsNone(snap["current_gate"])


class CliTests(unittest.TestCase):
    def test_human_commands_refuse_without_tty(self):
        import subprocess
        r = subprocess.run([sys.executable, str(REPO / "engine" / "board.py"), "approve", "rfp_lock",
                            "--member", "chair", "--decision", "APPROVE", "--evidence", "README.md"],
                           input="guess\n", capture_output=True, text=True, start_new_session=True)
        self.assertEqual(r.returncode, 2)
        self.assertIn("HUMAN ONLY", r.stderr)


if __name__ == "__main__":
    unittest.main()
