"""Budget (twlib.budget, twlib.dates.period_range) and its CLI output."""
import json, os
import unittest

from tests.helpers import tw, reply, write_session, CliRunner


class Budget(unittest.TestCase):
    D = __import__("datetime").date
    TODAY = D(2026, 11, 9)

    def test_period_ranges(self):
        self.assertEqual(tw.period_range("day", self.TODAY), (self.TODAY, self.TODAY))
        self.assertEqual(tw.period_range("week", self.TODAY)[0], self.D(2026, 11, 3))
        self.assertEqual(tw.period_range("month", self.TODAY)[0], self.D(2026, 11, 1))

    def test_parse_from_flags_and_env(self):
        self.assertEqual(tw.parse_budget(["--budget", "20"], {}), (20.0, "week"))
        self.assertEqual(tw.parse_budget(["--budget", "5", "--period", "day"], {}), (5.0, "day"))
        self.assertEqual(tw.parse_budget([], {"TOKENWATCH_BUDGET": "30/month"}), (30.0, "month"))
        self.assertEqual(tw.parse_budget([], {"TOKENWATCH_BUDGET": "30"}), (30.0, "week"))
        self.assertIsNone(tw.parse_budget([], {}))

    def test_flag_beats_env(self):
        self.assertEqual(tw.parse_budget(["--budget", "1"], {"TOKENWATCH_BUDGET": "9/day"}), (1.0, "week"))

    def test_bad_values_raise(self):
        for argv, env in ((["--budget", "-1"], {}), (["--budget", "x"], {}), (["--budget", "5", "--period", "year"], {}),
                          ([], {"TOKENWATCH_BUDGET": "0"})):
            with self.assertRaises(ValueError):
                tw.parse_budget(argv, env)

    def test_levels(self):
        self.assertEqual(tw.budget_status(5, 20, "week")["level"], "ok")
        self.assertEqual(tw.budget_status(16, 20, "week")["level"], "warn")
        self.assertEqual(tw.budget_status(20, 20, "week")["level"], "over")

    def test_budget_line_caps_bar(self):
        line = tw.budget_line(tw.budget_status(100, 20, "day"))
        self.assertIn("over budget", line)
        self.assertEqual(line.count("▓"), 10)

    def test_daily_cost_splits_across_midnight(self):
        f = write_session([reply("a", ts="2026-10-01T12:00:00Z", output_tokens=1_000_000),
                           reply("b", ts="2026-10-05T12:00:00Z", output_tokens=1_000_000)])
        self.addCleanup(os.unlink, f)
        s = tw.scan_session(f)
        self.assertEqual(len(s["daily"]), 2)
        self.assertAlmostEqual(sum(s["daily"].values()), 20.0)
        self.assertAlmostEqual(tw.spend_between([s], self.D(2026, 10, 5), self.D(2026, 10, 6)), 10.0)


class BudgetCli(CliRunner, unittest.TestCase):
    def test_budget_in_json_and_text(self):
        out = json.loads(self.run_cli("--json", "--budget", "100", "--period", "month"))
        self.assertIn(out["budget"]["level"], ("ok", "warn", "over"))
        self.assertIn("budget", self.run_cli("--budget", "100", "--period", "month"))

    def test_no_budget_key_value_is_null(self):
        old = os.environ.pop("TOKENWATCH_BUDGET", None)
        try: self.assertIsNone(json.loads(self.run_cli("--json"))["budget"])
        finally:
            if old: os.environ["TOKENWATCH_BUDGET"] = old


if __name__ == "__main__":
    unittest.main()
