"""The pr-reviewer agent stays read-only, stays a project agent (never shipped in the plugin) and stays aimed at
this repo's rules, so editing it can't quietly turn it into a rubber stamp."""
import os, re, subprocess, unittest

from tests.helpers import ROOT

AGENT = os.path.join(ROOT, ".claude", "agents", "pr-reviewer.md")
WRITERS = {"Write", "Edit", "NotebookEdit", "Agent", "Task", "MultiEdit"}


def parts():
    with open(AGENT, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"---\n(.*?)\n---\n(.*)", text, re.S)
    assert m, "agent file needs frontmatter"
    meta = dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line)
    return meta, m.group(2)


class ReviewerAgent(unittest.TestCase):
    def test_frontmatter(self):
        meta, _ = parts()
        self.assertEqual(meta["name"], "pr-reviewer")
        self.assertEqual(meta["name"], os.path.basename(AGENT)[:-3])
        self.assertGreater(len(meta["description"]), 80)
        for word in ("BLOCK", "FIX FIRST", "MERGE", "Never edits"):
            self.assertIn(word, meta["description"])

    def test_read_only_tools(self):
        tools = {t.strip() for t in parts()[0]["tools"].split(",")}
        self.assertEqual(tools & WRITERS, set(), "the reviewer must not be able to edit files or spawn agents")
        self.assertTrue({"Read", "Bash"} <= tools)          # it has to read the diff and run the tests

    def test_it_is_told_not_to_change_anything(self):
        body = parts()[1]
        for phrase in ("Read-only", "never edit", "push, merge", "mktemp -d"):
            self.assertIn(phrase.lower(), body.lower(), phrase)

    def test_it_checks_this_repos_rules(self):
        body = parts()[1]
        for needle in ("unittest discover", "demo.py --check", "leak scan", "mutation", "cache.VERSION", "args.FLAGS",
                       "plugin.json", "co-author", "No network", "~/.claude", "BLOCK", "FIX FIRST", "MERGE",
                       "Decoration", "Speculative", "Theatre"):
            self.assertIn(needle.lower(), body.lower(), needle)

    def test_every_hard_rule_in_claude_md_is_covered(self):
        """Each rule in CLAUDE.md's 'Hard rules' maps to a phrase the reviewer is told to enforce. Adding a fifth
        rule fails this until the reviewer (and this map) learn about it."""
        with open(os.path.join(ROOT, "CLAUDE.md"), encoding="utf-8") as fh:
            rules = re.search(r"## Hard rules\n\n(.*?)\n\n## ", fh.read(), re.S).group(1)
        leads = re.findall(r"^- \*\*(.+?)\*\*", rules, re.M)
        covered = {"Local only.": "no network calls", "Read-only on transcripts.": "never to `~/.claude`",
                   "No dependencies.": "standard library only", "Output stays short and plain.": "output stays short"}
        self.assertEqual(sorted(leads), sorted(covered), "CLAUDE.md's hard rules changed: update the reviewer")
        body = " ".join(parts()[1].lower().split())
        for lead, phrase in covered.items():
            self.assertIn(phrase, body, lead)

    def test_report_format_has_the_sections(self):
        body = parts()[1]
        for section in ("VERDICT:", "RAN:", "BLOCK", "FIX FIRST", "BULLSHIT", "WORTH KEEPING", "QUESTIONS"):
            self.assertIn(section, body)

    def test_not_shipped_in_the_plugin(self):
        self.assertFalse(os.path.isdir(os.path.join(ROOT, "agents")), "a root agents/ folder would ship to every user")
        self.assertFalse(os.path.exists(os.path.join(ROOT, "commands", "pr-reviewer.md")))

    def test_git_does_not_ignore_it(self):
        r = subprocess.run(["git", "check-ignore", "--no-index", "-q", AGENT], cwd=ROOT)
        self.assertEqual(r.returncode, 1, "gitignore hides the agent file (exit 1 means not ignored)")

    def test_documented_where_people_look(self):
        for name, needle in (("CLAUDE.md", "pr-reviewer"), ("README.md", "pr-reviewer")):
            with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
                self.assertIn(needle, fh.read(), name)


if __name__ == "__main__":
    unittest.main()
