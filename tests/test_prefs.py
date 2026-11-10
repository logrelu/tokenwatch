"""Saved settings (twlib.prefs), --save, and how the saved budget/theme reach the report and dashboard.
config.PREFS points at a throwaway file here (tests/__init__.py), never ~/.config."""
import io, json, os, shutil, sys, tempfile, unittest
from contextlib import redirect_stdout

from tests.helpers import ROOT, CliRunner, tw
from tests.test_open import OpenCase
from twlib import config, prefs


class PrefsCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)
        old = config.PREFS
        config.PREFS = os.path.join(self.dir, "tokenwatch", "config.json")
        self.addCleanup(setattr, config, "PREFS", old)

    def file(self):
        with open(config.PREFS, encoding="utf-8") as fh:
            return json.load(fh)

    def write(self, text):
        os.makedirs(os.path.dirname(config.PREFS), exist_ok=True)
        with open(config.PREFS, "w", encoding="utf-8") as fh: fh.write(text)


class Store(PrefsCase):
    def test_missing_file_is_empty(self):
        self.assertEqual(prefs.load(), {})

    def test_save_merges_and_none_removes(self):
        prefs.save({"budget": "25/week"})
        prefs.save({"theme": "weather"})
        self.assertEqual(self.file(), {"budget": "25/week", "theme": "weather"})
        prefs.save({"budget": None})
        self.assertEqual(prefs.load(), {"theme": "weather"})

    def test_rejects_bad_values_without_touching_the_file(self):
        prefs.save({"budget": "25/week"})
        for change in ({"budget": "-5/week"}, {"budget": "5/year"}, {"budget": "nan"}, {"theme": "neon"}, {"colour": "red"}):
            with self.assertRaises(ValueError):
                prefs.save(change)
        self.assertEqual(self.file(), {"budget": "25/week"})

    def test_broken_or_hand_edited_file_is_ignored(self):
        for text in ("{oops", "[1, 2]", '{"budget": "lots", "theme": "weather"}'):
            self.write(text)
            self.assertEqual(prefs.load(), {} if "theme" not in text else {"theme": "weather"})

    def test_no_temp_files_left_behind(self):
        prefs.save({"budget": "5/day"})
        self.assertEqual(os.listdir(os.path.dirname(config.PREFS)), ["config.json"])

    def test_describe(self):
        self.assertEqual(prefs.describe({}), "nothing saved")
        self.assertEqual(prefs.describe({"budget": "2.5/day", "theme": "weather"}), "budget $2.5 per day, theme weather")

    def test_default_location_is_outside_claude(self):
        import importlib
        before = dict(vars(config))              # reload resets every path; put them all back afterwards
        try:
            fresh = importlib.reload(config)
            self.assertTrue(fresh.PREFS.endswith(os.path.join("tokenwatch", "config.json")))
            self.assertNotIn(".claude", fresh.PREFS)
        finally:
            vars(config).update(before)


class BudgetOrder(PrefsCase):
    def test_flag_then_env_then_saved(self):
        saved = {"budget": "9/month"}
        self.assertEqual(tw.parse_budget([], {}, saved), (9.0, "month"))
        self.assertEqual(tw.parse_budget([], {"TOKENWATCH_BUDGET": "3/day"}, saved), (3.0, "day"))
        self.assertEqual(tw.parse_budget(["--budget", "1"], {"TOKENWATCH_BUDGET": "3/day"}, saved), (1.0, "week"))

    def test_saved_file_is_used_by_default(self):
        prefs.save({"budget": "40/month"})
        self.assertEqual(tw.parse_budget([], {}), (40.0, "month"))

    def test_slash_form_on_the_flag(self):
        self.assertEqual(tw.parse_budget(["--budget", "5/day"], {}), (5.0, "day"))
        with self.assertRaises(ValueError):
            tw.parse_budget(["--budget", "5/fortnight"], {})


class SaveFlag(PrefsCase, CliRunner):
    def test_save_budget_and_theme(self):
        said = self.run_cli("--budget", "25", "--period", "week", "--theme", "weather", "--save")
        self.assertIn("budget $25 per week, theme weather", said)
        self.assertIn(config.PREFS, said)
        self.assertEqual(self.file(), {"budget": "25/week", "theme": "weather"})

    def test_off_and_classic_forget(self):
        self.run_cli("--budget", "5/day", "--theme", "weather", "--save")
        self.run_cli("--budget", "off", "--save")
        self.run_cli("--theme", "classic", "--save")
        self.assertEqual(self.file(), {})

    def test_show_does_not_create_a_file(self):
        self.assertIn("nothing saved", self.run_cli("--save"))
        self.assertFalse(os.path.exists(config.PREFS))

    def test_bad_input_exits_and_saves_nothing(self):
        for argv in (("--budget", "-3", "--save"), ("--theme", "neon", "--save"), ("--week", "--save")):
            with self.assertRaises(SystemExit):
                self.run_cli(*argv)
        self.assertFalse(os.path.exists(config.PREFS))

    def test_bad_period_says_period(self):
        with self.assertRaises(SystemExit) as e:
            self.run_cli("--budget", "2", "--period", "dya", "--save")
        self.assertIn("day, week or month", str(e.exception.code))

    def test_report_shows_saved_budget(self):
        self.assertNotIn("💰", self.run_cli())
        prefs.save({"budget": "100/week"})
        self.assertIn("of $100 budget", self.run_cli())


class SavedTheme(OpenCase):
    def setUp(self):
        super().setUp()
        old = config.PREFS
        config.PREFS = os.path.join(os.path.dirname(self.out), "prefs.json")
        self.addCleanup(setattr, config, "PREFS", old)

    def page(self, *argv):
        self.cli("--open", *argv)
        with open(os.path.join(self.out, "dashboard.html"), encoding="utf-8") as fh:
            return fh.read().lower()

    def test_saved_theme_used_and_flag_wins(self):
        classic = self.page()
        prefs.save({"theme": "weather"})
        self.assertNotEqual(self.page(), classic)
        self.assertEqual(self.page("--theme", "classic"), classic)


class Command(unittest.TestCase):
    def test_budget_command_saves_with_the_cli(self):
        with open(os.path.join(ROOT, "commands", "budget.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn('tokenwatch.py" --budget off --save', text)
        self.assertIn('tokenwatch.py" --save', text)


class Isolation(unittest.TestCase):
    def test_tests_never_use_the_real_settings_file(self):
        self.assertIn("tokenwatch-tests-", config.PREFS)


if __name__ == "__main__":
    unittest.main()
