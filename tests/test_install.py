"""The version-independent statusline command, its setup instructions and the greeting's reminder.
Everything runs against fake plugin folders in a temp dir, never the real ~/.claude."""
import io, json, os, shutil, subprocess, sys, tempfile, unittest
from contextlib import redirect_stdout

from tests.helpers import ROOT
from twlib import config, install

CACHE = ("plugins", "cache", "tokenwatch", "tokenwatch")


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def fake_install(root, *versions):
    for v in versions:
        d = os.path.join(root, *CACHE, v)
        os.makedirs(d)
        with open(os.path.join(d, "statusline.py"), "w") as fh:
            fh.write("import sys\nprint(%r, sys.stdin.read().strip())\n" % v)


class Command(unittest.TestCase):
    def run_cmd(self, config_dir, stdin="", cwd=None):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=config_dir)
        return subprocess.run(install.STATUSLINE_COMMAND, shell=True, input=stdin, capture_output=True,
                              text=True, env=env, cwd=cwd or tempfile.gettempdir(), timeout=20)

    def setUp(self):
        self.root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.root)

    def test_runs_the_newest_version_compared_as_numbers(self):
        fake_install(self.root, "0.4.0", "0.9.0", "0.10.0")
        r = self.run_cmd(self.root, stdin='{"x": 1}')
        self.assertEqual(r.stdout.strip(), '0.10.0 {"x": 1}')
        self.assertEqual(r.returncode, 0)

    def test_nothing_installed_is_silent(self):
        r = self.run_cmd(self.root)
        self.assertEqual((r.stdout, r.returncode), ("", 0))

    def test_ignores_modules_in_the_current_project(self):
        fake_install(self.root, "1.0.0")
        project = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, project)
        with open(os.path.join(project, "glob.py"), "w") as fh:
            fh.write("raise SystemExit('project module ran')\n")
        r = self.run_cmd(self.root, cwd=project)
        self.assertEqual(r.stdout.strip(), "1.0.0")

    def test_has_no_version_or_home_path(self):
        self.assertNotRegex(install.STATUSLINE_COMMAND, r"\d+\.\d+\.\d+|/Users/|/home/")


class Pinned(unittest.TestCase):
    def test_finds_old_pinned_setup(self):
        s = {"statusLine": {"command": 'python3 "/x/.claude/plugins/cache/tokenwatch/tokenwatch/0.4.0/statusline.py"'}}
        self.assertEqual(install.pinned_version(s), "0.4.0")

    def test_new_command_manual_and_missing_are_not_pinned(self):
        for s in ({"statusLine": install.STATUSLINE}, {"statusLine": {"command": "python3 /x/tokenwatch/statusline.py"}},
                  {}, None, {"statusLine": None}):
            self.assertIsNone(install.pinned_version(s))

    def test_read_settings_tolerates_bad_files(self):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        bad = os.path.join(d, "s.json")
        with open(bad, "w") as fh: fh.write("{not json")
        self.assertEqual(install.read_settings(bad), {})
        self.assertEqual(install.read_settings(os.path.join(d, "missing.json")), {})


class Verify(unittest.TestCase):
    def check(self, settings):
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d)
        path = os.path.join(d, "settings.json")
        with open(path, "w") as fh: json.dump(settings, fh)
        before = read(path)
        with redirect_stdout(io.StringIO()) as out:
            ok = install.verify(path)
        self.assertEqual(read(path), before)                 # read-only
        return ok, out.getvalue()

    def test_match_and_mismatch(self):
        self.assertTrue(self.check({"statusLine": install.STATUSLINE, "model": "opus"})[0])
        ok, said = self.check({"statusLine": {"type": "command", "command": "python3 x"}})
        self.assertFalse(ok)
        self.assertIn(json.dumps(install.STATUSLINE), said)


class SetupCommand(unittest.TestCase):
    def test_setup_md_has_exactly_the_command_and_verifies(self):
        with open(os.path.join(ROOT, "commands", "setup.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn(json.dumps(install.STATUSLINE), text)
        self.assertIn('twlib/install.py" --verify', text)
        self.assertNotIn("re-run", text.lower())


class Greeting(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, ROOT)
        import sessionstart
        self.ss = sessionstart
        self.d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.d)
        old = config.SETTINGS
        config.SETTINGS = os.path.join(self.d, "settings.json")
        self.addCleanup(setattr, config, "SETTINGS", old)

    def write(self, settings):
        with open(config.SETTINGS, "w") as fh: json.dump(settings, fh)

    def test_reminds_when_pinned(self):
        self.write({"statusLine": {"command": "python3 /h/.claude/plugins/cache/tokenwatch/tokenwatch/0.4.0/statusline.py"}})
        line = self.ss.setup_reminder()
        self.assertIn("pinned to plugin 0.4.0", line)
        self.assertIn("/tokenwatch:setup", line)

    def test_quiet_otherwise(self):
        self.assertIsNone(self.ss.setup_reminder())               # no settings file
        self.write({"statusLine": install.STATUSLINE})
        self.assertIsNone(self.ss.setup_reminder())


if __name__ == "__main__":
    unittest.main()
