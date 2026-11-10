"""The plugin's commands and skill stay in sync with the CLI they call."""
import glob, json, os, re, unittest

from tests.helpers import ROOT, CliRunner
from twlib import args

COMMANDS = sorted(glob.glob(os.path.join(ROOT, "commands", "*.md")))
SKILL = os.path.join(ROOT, "skills", "tokenwatch", "SKILL.md")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def frontmatter(text):
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return dict(line.split(": ", 1) for line in m.group(1).splitlines() if ": " in line) if m else {}


class Commands(unittest.TestCase):
    def test_every_command_has_a_description(self):
        self.assertGreaterEqual(len(COMMANDS), 7)
        for path in COMMANDS:
            self.assertTrue(frontmatter(read(path)).get("description"), path)

    def test_every_run_line_has_a_plain_text_fallback(self):
        for path in COMMANDS:
            text = read(path)
            for cmd in re.findall(r"^!`(.+)`$", text, re.M):
                self.assertIn("If no output appears above", text, path)
                self.assertIn("`%s` with Bash" % cmd, text, path)

    def test_commands_only_use_known_flags(self):
        # pet.md (pet.py's own options) and setup.md (install.py --verify) don't call tokenwatch.py
        for path in [p for p in COMMANDS if os.path.basename(p) not in ("pet.md", "setup.md")] + [SKILL]:
            for flag in re.findall(r"(?<![\w-])--[a-z][a-z-]*", read(path)):
                self.assertIn(flag, args.FLAGS, f"{os.path.basename(path)} uses unknown {flag}")

    def test_quick_commands_leave_questions_to_the_skill(self):
        # "how much did I spend today?" should get the skill's plain-English answer, not a raw report
        for name in ("today", "week"):
            self.assertEqual(frontmatter(read(os.path.join(ROOT, "commands", name + ".md"))).get("disable-model-invocation"), "true")

    def test_today_and_week(self):
        self.assertIn('tokenwatch.py" --today', read(os.path.join(ROOT, "commands", "today.md")))
        self.assertIn('tokenwatch.py" --week', read(os.path.join(ROOT, "commands", "week.md")))


class Skill(CliRunner, unittest.TestCase):
    def test_frontmatter(self):
        fm = frontmatter(read(SKILL))
        self.assertEqual(fm.get("name"), "tokenwatch")
        for word in ("spent", "expensive", "budget", "tokens"):
            self.assertIn(word, fm.get("description", ""))

    def test_uses_the_plugin_copy_only(self):
        text = read(SKILL)
        self.assertIn('"${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --json', text)
        self.assertIn("Do not search for other copies", text)

    def test_json_fields_it_describes_exist(self):
        text = read(SKILL)
        report = json.loads(self.run_cli("--json"))
        session = report["projects"][0]["sessions"][0]
        for key in ("total_cost", "total_tokens", "budget", "projects"):
            self.assertIn(key, report)
        for key in ("cost", "tips", "sessions"):
            self.assertIn(key, report["projects"][0])
        for key in ("start", "model", "turns", "cost", "cost_as_cheaper", "spent", "peak_context", "cold_restarts", "tips", "agents", "agent_cost"):
            self.assertIn(key, session)
            self.assertIn("`%s`" % key, text)
        for key in ("read", "write", "out", "in"):
            self.assertIn(key, session["spent"])
        daily = json.loads(self.run_cli("--daily", "--json", "--since", "2026-10-01", "--until", "2026-10-02"))
        self.assertEqual(set(daily), {"days", "total_cost"})
        self.assertEqual(set(daily["days"][0]), {"date", "cost"})


if __name__ == "__main__":
    unittest.main()
