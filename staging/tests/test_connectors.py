"""Connector, skill script and guard tests. Run: python3 -m unittest discover -s tests -v"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / "engine" / "board.py").exists():
            return p
        p = p.parent
    raise RuntimeError("repo root not found")


REPO = _repo_root()
HERE_ROOT = Path(__file__).resolve().parent.parent  # repo root once installed, staging/ before install
SKILLS = HERE_ROOT / ".claude" / "skills"
HOOK = HERE_ROOT / ".claude" / "hooks" / "guard_state.py"

TMP = Path(tempfile.mkdtemp())
(TMP / "state").mkdir()
for f in ("raci_gates.json", "syrian_market_constraints.json"):
    shutil.copy(REPO / "state" / f, TMP / "state" / f)
rules = json.loads((TMP / "state" / "raci_gates.json").read_text(encoding="utf-8"))
rules["controlled_actions"]["test_noop"] = {"label_en": "test", "conditions": []}
(TMP / "state" / "raci_gates.json").write_text(json.dumps(rules), encoding="utf-8")
(TMP / "packets").mkdir()
os.environ["BOARD_ROOT"] = str(TMP)
os.environ.pop("TELEGRAM_BOT_TOKEN", None)
os.environ.pop("M365_CLIENT_ID", None)
sys.path.insert(0, str(REPO / "connectors"))
sys.path.insert(0, str(REPO / "engine"))
import board as engine  # noqa: E402
import outbound_policy  # noqa: E402
import telegram_mcp  # noqa: E402
import m365_drafts_mcp  # noqa: E402
from mcp_stdio import ToolError  # noqa: E402


def tearDownModule():
    shutil.rmtree(TMP, ignore_errors=True)


class LedgerMcpTests(unittest.TestCase):
    def test_protocol_and_read_only(self):
        b = engine.Board(TMP)
        before = len(b.events())
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "board_status", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
             "params": {"name": "authorize_dry_run", "arguments": {"action": "book_expert_travel"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
             "params": {"name": "read_document", "arguments": {"kind": "packets", "name": "../state/raci_gates.json"}}},
        ]
        r = subprocess.run([sys.executable, str(REPO / "connectors" / "board_ledger_mcp.py")],
                           input="\n".join(json.dumps(m) for m in msgs) + "\n",
                           capture_output=True, text=True, env=os.environ, timeout=30)
        out = {o["id"]: o for o in map(json.loads, r.stdout.splitlines())}
        self.assertIn(1, out, r.stderr[-2000:])
        self.assertEqual(out[1]["result"]["serverInfo"]["name"], "board-ledger")
        self.assertEqual(len(out[2]["result"]["tools"]), 6)
        status = json.loads(out[3]["result"]["content"][0]["text"])
        self.assertEqual(status["current_gate"], "G1")
        dry = json.loads(out[4]["result"]["content"][0]["text"])
        self.assertFalse(dry["would_allow"])
        self.assertTrue(out[5]["result"]["isError"])  # path traversal refused
        self.assertEqual(len(b.events()), before)  # nothing written


class OutboundPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        b = engine.Board(TMP)
        cls.deny = b.authorize("book_expert_travel", None, "t")[2]["seq"]
        cls.allow = b.authorize("test_noop", None, "t")[2]["seq"]

    def test_status_update_draft_written_not_sent(self):
        res = telegram_mcp.queue_draft({"text": "البوابة G1 مغلقة | G1 blocked", "kind": "status_update"})
        p = TMP / res["draft"]
        self.assertTrue(p.exists())
        self.assertIn('"status": "DRAFT"', p.read_text(encoding="utf-8"))
        self.assertIn("telegram_send.py", res["send_command"])

    def test_instruction_requires_authorization(self):
        with self.assertRaises(ToolError):
            telegram_mcp.queue_draft({"text": "Book flights", "kind": "instruction"})
        with self.assertRaises(ToolError):
            telegram_mcp.queue_draft({"text": "Book flights", "kind": "instruction", "auth_seq": self.deny})
        with self.assertRaises(ToolError):
            telegram_mcp.queue_draft({"text": "x", "kind": "instruction", "auth_seq": self.allow,
                                      "action": "book_expert_travel"})
        res = telegram_mcp.queue_draft({"text": "ok", "kind": "instruction", "auth_seq": self.allow})
        self.assertIn(f"auth seq {self.allow}", (TMP / res["draft"]).read_text(encoding="utf-8"))

    def test_outlook_policy_checked_before_network(self):
        with self.assertRaises(ToolError) as cm:
            m365_drafts_mcp.create_draft({"subject": "Pay vendor", "kind": "instruction", "to": ["a@b.com"]})
        self.assertIn("auth_seq", str(cm.exception))

    def test_upload_restricted(self):
        with self.assertRaises(ToolError):
            m365_drafts_mcp.upload_draft({"path": "state/raci_gates.json"})
        (TMP / "packets" / "p.md").write_text("[[UNVERIFIED]] draft", encoding="utf-8")
        with self.assertRaises(ToolError) as cm:
            m365_drafts_mcp.upload_draft({"path": "packets/p.md"})
        self.assertIn("UNVERIFIED", str(cm.exception))

    def test_no_send_scope(self):
        import m365_auth
        self.assertNotIn("Mail.Send", m365_auth.SCOPES)
        self.assertNotIn("Files.ReadWrite ", m365_auth.SCOPES + " ")


class SkillScriptTests(unittest.TestCase):
    def run_script(self, rel, *args):
        r = subprocess.run([sys.executable, str(SKILLS / rel), *args], capture_output=True, text=True, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def test_press_calc(self):
        out = self.run_script("extrusion-press-sizing/scripts/press_calc.py", "--force-usTon", "1800",
                              "--container-mm", "178", "--billet-dia-mm", "170", "--billet-len-mm", "650",
                              "--profile-area-mm2", "450", "--holes", "2", "--ram-mm-s", "8",
                              "--dead-cycle-s", "22", "--alloy", "6063")
        self.assertAlmostEqual(out["force_MN"], 16.01, places=1)
        self.assertTrue(600 < out["specific_pressure_MPa"] < 680)
        self.assertTrue(25 < out["extrusion_ratio"] < 30)

    def test_cpm_merge(self):
        f = TMP / "sched.csv"
        rows = [("C", "contract", "B", 0, ""), ("DWG", "drawings", "B", 42, "C"), ("POUR", "pour", "A", 60, "DWG"),
                ("CURE", "cure", "A", 28, "POUR"), ("MFG", "manufacture", "B", 150, "C"),
                ("SHIP", "ship", "B", 35, "MFG"), ("READY", "site ready", "A", 0, "CURE;SHIP")]
        with open(f, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["id", "name", "track", "duration_days", "depends_on"])
            w.writerows(rows)
        out = self.run_script("critical-path-scheduling/scripts/cpm.py", str(f), "--start", "2027-01-01",
                              "--merge-task", "READY")
        self.assertEqual(out["duration_days"], 185)
        self.assertEqual(out["merge"]["driver"], "SHIP")
        self.assertIn("MFG", out["critical_path"])

    def test_depreciation(self):
        out = self.run_script("capex-accounting-ifrs/scripts/depreciation.py", "--component", "Press",
                              "--cost", "1200000", "--residual", "0", "--life-years", "20",
                              "--available-for-use", "2027-07", "--years", "2")
        self.assertEqual(out["first_month_charge"], "5000.00")
        self.assertEqual(out["yearly"][0]["depreciation"], "30000.00")


class GuardTests(unittest.TestCase):
    def hook(self, payload):
        env = {k: v for k, v in os.environ.items() if k != "BOARD_MAINTENANCE"}
        env["CLAUDE_PROJECT_DIR"] = str(REPO)
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                              capture_output=True, text=True, env=env).returncode

    def test_mcp_policy(self):
        cases = {
            "mcp__board-ledger__board_status": 0,
            "mcp__board-ledger__authorize_dry_run": 0,
            "mcp__claude_ai_Microsoft_365__sharepoint_search": 0,
            "mcp__claude_ai_Microsoft_365__read_resource": 0,
            "mcp__m365-drafts__outlook_create_draft": 0,
            "mcp__telegram-board__telegram_queue_draft": 0,
            "mcp__claude_ai_Gmail__send_email": 2,
            "mcp__Google_Drive__share_file": 2,
            "mcp__Google_Drive__create_file": 2,
            "mcp__Supabase__execute_sql": 2,
            "mcp__github__push_files": 2,
            "mcp__somevendor__do_magic": 2,
        }
        for tool, want in cases.items():
            self.assertEqual(self.hook({"tool_name": tool, "tool_input": {}}), want, tool)

    def test_bash_policy(self):
        cases = {
            "python3 connectors/telegram_send.py outbox/telegram/x.md": 2,
            "python3 connectors/m365_login.py": 2,
            "python3 staging/install.py": 2,
            "BOARD_MAINTENANCE=1 python3 -c 'pass'": 2,
            "rm -rf connectors": 2,
            "python3 .claude/skills/critical-path-scheduling/scripts/cpm.py specs/schedule.csv": 0,
            "python3 engine/board.py status": 0,
        }
        for cmd, want in cases.items():
            self.assertEqual(self.hook({"tool_name": "Bash", "tool_input": {"command": cmd}}), want, cmd)

    def test_protected_files(self):
        for path in (".mcp.json", "connectors/telegram_mcp.py", ".claude/skills/x/SKILL.md"):
            self.assertEqual(self.hook({"tool_name": "Write", "tool_input": {"file_path": path}}), 2, path)
        self.assertEqual(self.hook({"tool_name": "Write", "tool_input": {"file_path": "packets/a.md"}}), 0)


if __name__ == "__main__":
    unittest.main()
