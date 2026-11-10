"""Subagent transcripts (<session>/subagents/*.jsonl) count toward the session that started them.
Synthetic transcripts in a temp folder laid out the way Claude Code saves them; never real data."""
import contextlib, io, json, os, shutil, sys, tempfile, time, unittest
from datetime import date

from tests.helpers import reply
import tokenwatch as tw
from twlib import config
from twlib.budget import _changed_since, spend_between
from twlib.scan import last_modified, scan_project, scan_session, subagent_files

OPUS, HAIKU = "claude-opus-5-5", "claude-haiku-4-5"
DAY = "2026-10-01T10:%02d:00Z"


def lines_to(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        fh.write("".join(json.dumps(d) + "\n" for d in lines))
    return path


class Layout(unittest.TestCase):
    """projects/-Users-me-app/s1.jsonl plus s1/subagents/agent-*.jsonl and the other files Claude Code keeps."""

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)
        self.pdir = os.path.join(self.root, "-Users-me-app")
        self.main = lines_to(os.path.join(self.pdir, "s1.jsonl"), [
            reply("m1", OPUS, DAY % 0, output_tokens=1_000, cache_creation_input_tokens=10_000),
            reply("m2", OPUS, DAY % 5, output_tokens=1_000, cache_read_input_tokens=10_000)])
        sub = os.path.join(self.pdir, "s1", "subagents")
        # an agent with three content-block lines for one reply (counted once) and a second reply
        a = reply("x1", HAIKU, DAY % 1, output_tokens=2_000, cache_creation_input_tokens=200_000)
        lines_to(os.path.join(sub, "agent-a1.jsonl"), [dict(a, isSidechain=True)] * 3 + [
            dict(reply("x2", HAIKU, DAY % 2, output_tokens=2_000), isSidechain=True)])
        lines_to(os.path.join(sub, "agent-a2.jsonl"), [reply("y1", OPUS, DAY % 3, output_tokens=4_000)])
        lines_to(os.path.join(sub, "agent-empty.jsonl"), [{"type": "user", "message": {"content": "hi"}}])
        with open(os.path.join(sub, "agent-a1.meta.json"), "w") as fh: json.dump({"agentType": "Explore"}, fh)
        # files Claude Code keeps beside sessions that are NOT usage and must not be counted
        lines_to(os.path.join(self.pdir, "s1", "skill-injections.jsonl"), [reply("no1", OPUS, DAY % 4, output_tokens=9_000_000)])
        lines_to(os.path.join(self.pdir, "s1", "tool-results", "r.jsonl"), [reply("no2", OPUS, DAY % 4, output_tokens=9_000_000)])
        os.makedirs(os.path.join(self.root, "solo"))           # the same main transcript with no subagents
        self.alone = scan_session(shutil.copy(self.main, os.path.join(self.root, "solo", "s1.jsonl")))


class ScanSession(Layout):
    def test_finds_only_the_subagents_folder(self):
        self.assertEqual([os.path.basename(f) for f in subagent_files(self.main)],
                         ["agent-a1.jsonl", "agent-a2.jsonl", "agent-empty.jsonl"])
        self.assertEqual(subagent_files(os.path.join(self.root, "nothing.jsonl")), [])

    def test_agent_cost_is_added_and_reported(self):
        s = scan_session(self.main)
        a1 = scan_session(os.path.join(self.pdir, "s1", "subagents", "agent-a1.jsonl"))
        a2 = scan_session(os.path.join(self.pdir, "s1", "subagents", "agent-a2.jsonl"))
        self.assertGreater(a1["cost"], 0)
        self.assertAlmostEqual(s["cost"], self.alone["cost"] + a1["cost"] + a2["cost"])
        self.assertAlmostEqual(s["agent_cost"], a1["cost"] + a2["cost"])
        self.assertEqual(s["agents"], 2)                    # the agent with no replies isn't counted
        self.assertEqual(s["agent_turns"], 3)               # x1 once despite three lines, x2, y1
        self.assertEqual(s["tokens"]["output_tokens"], 2_000 + 2_000 + 2_000 + 4_000)
        self.assertAlmostEqual(sum(s["daily"].values()), s["cost"])

    def test_main_conversation_figures_are_unchanged(self):
        s = scan_session(self.main)
        for k in ("turns", "start", "model", "peak", "context", "first_write", "rebuilds"):
            self.assertEqual(s[k], self.alone[k], k)        # a 200K agent write is not a cold restart

    def test_skill_injections_and_tool_results_are_ignored(self):
        self.assertLess(scan_session(self.main)["tokens"]["output_tokens"], 9_000_000)

    def test_project_totals_include_agents(self):
        p = scan_project(self.pdir)
        self.assertEqual(len(p["sessions"]), 1)
        self.assertAlmostEqual(p["cost"], scan_session(self.main)["cost"])

    def test_no_subagents_means_zero(self):
        self.assertEqual((self.alone["agents"], self.alone["agent_cost"]), (0, 0.0))


class Mtime(Layout):
    def test_a_recent_agent_keeps_an_old_session_in_range(self):
        old = time.time() - 30 * 86400
        os.utime(self.main, (old, old))
        self.assertGreater(last_modified(self.main), old + 86400)
        saved = config.PROJECTS
        self.addCleanup(setattr, config, "PROJECTS", saved)
        config.PROJECTS = self.root
        self.assertIn(self.main, _changed_since(date.today()))
        for f in [self.main] + subagent_files(self.main): os.utime(f, (old, old))
        self.assertNotIn(self.main, _changed_since(date.today()))

    def test_missing_file_raises_oserror(self):
        with self.assertRaises(OSError): last_modified(os.path.join(self.root, "gone.jsonl"))


class Cli(Layout):
    def run_cli(self, *args):
        saved = (config.PROJECTS, sys.argv)
        config.PROJECTS, sys.argv = self.root, ["tokenwatch.py", *args]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out): tw.main()
        finally:
            config.PROJECTS, sys.argv = saved
        return out.getvalue()

    def test_session_line_says_what_agents_cost(self):
        out = self.run_cli("--project", "app")
        line = [l for l in out.splitlines() if l.lstrip().startswith("▸")][0]
        self.assertIn("· incl. 2 agents ≈$", line)

    def test_no_note_without_agents(self):
        out = self.run_cli("--project", "solo")
        self.assertNotIn("incl.", out)

    def test_json_fields(self):
        data = json.loads(self.run_cli("--json", "--project", "app"))
        s = data["projects"][0]["sessions"][0]
        self.assertEqual((s["agents"], s["agent_turns"]), (2, 3))
        self.assertAlmostEqual(s["agent_cost"], scan_session(self.main)["agent_cost"], places=4)
        self.assertAlmostEqual(data["total_cost"], scan_session(self.main)["cost"], places=3)

    def test_budget_counts_agent_spend(self):
        s = scan_session(self.main)
        self.assertAlmostEqual(spend_between([s], date(2026, 10, 1), date(2026, 10, 1)), s["cost"])
        self.assertGreater(s["cost"], self.alone["cost"])


if __name__ == "__main__":
    unittest.main()
