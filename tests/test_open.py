"""--open and /tokenwatch:dashboard: one step from command to browser. No real browser ever starts."""
import os, shutil, stat, tempfile, unittest

from tests.test_dashboard import DashboardCase
from tests.helpers import ROOT
from twlib import args, cli, config


class OpenCase(DashboardCase):
    def setUp(self):
        self.out = os.path.join(tempfile.mkdtemp(), "tokenwatch-test")
        self.addCleanup(shutil.rmtree, os.path.dirname(self.out))
        saved = (config.OUT_DIR, cli.open_browser)
        self.addCleanup(lambda: (setattr(config, "OUT_DIR", saved[0]), setattr(cli, "open_browser", saved[1])))
        config.OUT_DIR, self.opened = self.out, []
        cli.open_browser = lambda url: self.opened.append(url) or True
        self.projects()


class Open(OpenCase):
    def test_open_writes_to_private_folder_and_opens_it(self):
        said = self.cli("--open")
        path = os.path.join(self.out, "dashboard.html")
        self.assertTrue(os.path.isfile(path))
        self.assertIn(path, said)
        self.assertIn("opened in your browser", said)
        self.assertEqual(len(self.opened), 1)
        self.assertTrue(self.opened[0].startswith("file://") and self.opened[0].endswith("/dashboard.html"))

    def test_folder_is_readable_only_by_you(self):
        self.cli("--open")
        self.assertEqual(stat.S_IMODE(os.stat(self.out).st_mode), 0o700)

    def test_overwrites_instead_of_piling_up(self):
        self.cli("--open")
        self.cli("--open", "--theme", "weather")
        self.assertEqual(os.listdir(self.out), ["dashboard.html"])
        with open(os.path.join(self.out, "dashboard.html"), encoding="utf-8") as fh:
            self.assertIn("weather", fh.read().lower())

    def test_export_path_with_open_writes_there(self):
        path = os.path.join(os.path.dirname(self.out), "mine.html")
        self.cli("--export", "html", path, "--open")
        self.assertTrue(os.path.isfile(path))
        self.assertFalse(os.path.exists(self.out))
        self.assertTrue(self.opened[0].endswith("/mine.html"))

    def test_export_without_open_never_opens(self):
        self.cli("--export", "html", os.path.join(os.path.dirname(self.out), "x.html"))
        self.assertEqual(self.opened, [])

    def test_no_browser_prints_the_path_instead(self):
        cli.open_browser = lambda url: False
        said = self.cli("--open")
        self.assertIn("open the file above yourself", said)

    def test_browser_error_does_not_crash(self):
        def boom(url): raise RuntimeError("no display")
        cli.open_browser = boom
        self.assertIn("open the file above yourself", self.cli("--open"))

    def test_refuses_a_symlinked_folder(self):
        target = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, target)
        os.symlink(target, self.out)
        with self.assertRaises(SystemExit):
            self.cli("--open")
        self.assertEqual(os.listdir(target), [])
        self.assertEqual(self.opened, [])

    def test_bad_theme_still_rejected(self):
        with self.assertRaises(SystemExit):
            self.cli("--open", "--theme", "neon")
        self.assertEqual(self.opened, [])


class Flags(unittest.TestCase):
    def test_open_is_a_known_flag(self):
        self.assertIsNone(args.find_problem(["--open", "--week"]))
        self.assertIsNone(args.find_problem(["--export", "html", "/x/y.html", "--open"]))
        self.assertIn("--open", args.USAGE)

    def test_default_out_dir_is_temp_not_claude(self):
        self.assertTrue(config.OUT_DIR.startswith(tempfile.gettempdir()))
        self.assertNotIn(".claude", config.OUT_DIR)


class Command(unittest.TestCase):
    def test_dashboard_command_runs_open_and_has_a_fallback(self):
        with open(os.path.join(ROOT, "commands", "dashboard.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('!`python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --open $ARGUMENTS`', text)
        self.assertIn("If no output appears above", text)


if __name__ == "__main__":
    unittest.main()
