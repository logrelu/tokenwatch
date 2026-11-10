"""The weekly recap (twlib.recap), --recap / --no-recap, and the greeting showing it once per week.
Synthetic transcripts only; config paths point at temp folders."""
import json, os, shutil, sys, tempfile, unittest
from datetime import date, timedelta

from tests.helpers import ROOT, CliRunner
from tests.test_live_budget import LiveCase, write_reply
from twlib import config, prefs, recap

MON, TUE, SUN = date(2026, 11, 9), date(2026, 11, 10), date(2026, 11, 15)


def session(daily, name="~/app"):
    return (name, {"daily": daily})


class Weeks(unittest.TestCase):
    def test_last_week_is_monday_to_sunday(self):
        for today in (MON, TUE, SUN):
            last, before = recap.weeks(today)
            self.assertEqual(last, (date(2026, 11, 2), date(2026, 11, 8)))
            self.assertEqual(before, (date(2026, 10, 26), date(2026, 11, 1)))


class Line(unittest.TestCase):
    def test_summary_and_comparison(self):
        r = recap.summarize([session({date(2026, 11, 3): 10.0, date(2026, 10, 30): 4.0}, "~/a"),
                             session({date(2026, 11, 8): 2.0}, "~/b"),
                             session({date(2026, 11, 9): 99.0}, "~/c")], TUE)    # this week: not counted
        self.assertEqual((r["cost"], r["sessions"], r["top"], r["prev"]), (12.0, 2, ("~/a", 10.0), 4.0))
        self.assertEqual(recap.recap_line(r),
                         "📅 tokenwatch: last week (2 Nov – 8 Nov): ≈$12.00 over 2 sessions · priciest: ~/a ($10.00) · ↑ 200% vs the week before")

    def test_down_and_single_session(self):
        r = recap.summarize([session({date(2026, 11, 4): 3.0, date(2026, 10, 27): 6.0})], MON)
        self.assertEqual(recap.recap_line(r), "📅 tokenwatch: last week (2 Nov – 8 Nov): ≈$3.00 over 1 session · ↓ 50% vs the week before")

    def test_nothing_spent_means_no_line(self):
        self.assertIsNone(recap.recap_line(recap.summarize([session({date(2026, 10, 1): 5.0})], MON)))


class Once(LiveCase):
    def setUp(self):
        super().setUp()
        old = config.STATE
        config.STATE = os.path.join(self.tmp, "state", "recap.json")
        self.addCleanup(setattr, config, "STATE", old)
        write_reply(config.PROJECTS, "-Users-me-app", "s1", MON - timedelta(days=3), 1_000_000)   # last Friday, $10

    def test_shown_once_per_week(self):
        first = recap.greeting_line(MON)
        self.assertIn("≈$10.00 over 1 session", first)
        self.assertIsNone(recap.greeting_line(TUE))                   # same week
        self.assertTrue(recap.due(MON + timedelta(days=7)))           # a new week is due again

    def test_quiet_week_is_not_marked_shown(self):
        self.assertIsNone(recap.greeting_line(MON + timedelta(days=14)))
        self.assertFalse(os.path.exists(config.STATE))

    def test_turned_off(self):
        prefs.save({"recap": "off"})
        self.assertFalse(recap.due(MON))
        self.assertIsNone(recap.greeting_line(MON))

    def test_broken_state_file_means_due(self):
        os.makedirs(os.path.dirname(config.STATE))
        with open(config.STATE, "w") as fh: fh.write("[nonsense")
        self.assertTrue(recap.due(MON))

    def test_state_file_holds_only_the_week(self):
        recap.greeting_line(MON)
        with open(config.STATE, encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"shown_week": "2026-11-09"})

    def test_real_greeting_shows_it_once(self):
        """sessionstart.py in a sandboxed HOME: a reply 7 days ago is always in last week."""
        import subprocess
        home = os.path.join(self.tmp, "home")
        write_reply(os.path.join(home, ".claude", "projects"), "-Users-me-app", "s1", date.today() - timedelta(days=7), 1_000_000)
        env = {k: v for k, v in os.environ.items() if k not in ("TOKENWATCH_BUDGET", "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME", "CLAUDE_CONFIG_DIR")}
        env.update(HOME=home, TMPDIR=self.tmp, PYTHONIOENCODING="utf-8")
        run = lambda: subprocess.run([sys.executable, os.path.join(ROOT, "sessionstart.py")], input="{}",
                                     capture_output=True, text=True, env=env, timeout=30).stdout
        first, second = run(), run()
        self.assertIn("📅 tokenwatch: last week", first)
        self.assertIn("≈$10.00 over 1 session", first)
        self.assertNotIn("📅", second)
        self.assertTrue(os.path.exists(os.path.join(home, ".local", "state", "tokenwatch", "recap.json")))


class Flags(CliRunner, unittest.TestCase):
    def test_recap_flag_prints_even_when_empty(self):
        self.assertIn("nothing spent last week", self.run_cli("--recap"))

    def test_no_recap_needs_save(self):
        with self.assertRaises(SystemExit):
            self.run_cli("--no-recap")

    def test_save_off_and_back_on(self):
        self.assertIn("weekly recap off", self.run_cli("--no-recap", "--save"))
        self.assertEqual(prefs.load(), {"recap": "off"})
        self.run_cli("--recap", "--save")
        self.assertEqual(prefs.load(), {})

    def test_both_is_an_error(self):
        with self.assertRaises(SystemExit):
            self.run_cli("--recap", "--no-recap", "--save")

    def test_only_off_is_a_valid_saved_value(self):
        self.assertTrue(prefs.valid("recap", "off"))
        self.assertFalse(prefs.valid("recap", "on"))


class Isolation(unittest.TestCase):
    def test_tests_never_use_the_real_state_file(self):
        self.assertIn("tokenwatch-tests-", config.STATE)


if __name__ == "__main__":
    unittest.main()
