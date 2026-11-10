"""Daily trend (twlib.trend) and --daily CLI output."""
import json, os
import unittest

from tests.helpers import tw, reply, write_session, CliRunner


class Trend(unittest.TestCase):
    D = __import__("datetime").date

    def test_sparkline_scales_and_handles_zero(self):
        self.assertEqual(tw.sparkline([0, 0]), "▁▁")
        self.assertEqual(tw.sparkline([]), "")
        sp = tw.sparkline([0, 5, 10])
        self.assertEqual((sp[0], sp[-1]), ("▁", "█"))
        self.assertEqual(len(sp), 3)

    def test_daily_totals_zero_filled(self):
        f = write_session([reply("a", ts="2026-10-02T12:00:00Z", output_tokens=1_000_000)])
        self.addCleanup(os.unlink, f)
        days = tw.daily_totals([tw.scan_session(f)], self.D(2026, 10, 1), self.D(2026, 10, 3))
        self.assertEqual([d.day for d, _ in days], [1, 2, 3])
        self.assertEqual([c for _, c in days][0], 0.0)
        self.assertAlmostEqual(days[1][1], 10.0)

    def test_trend_lines_mark_busiest(self):
        days = [(self.D(2026, 10, 1), 1.0), (self.D(2026, 10, 2), 4.0)]
        out = "\n".join(tw.trend_lines(days))
        self.assertEqual(out.count("busiest"), 1)
        self.assertIn("02 Oct", out.split("busiest")[0].splitlines()[-1])

    def test_trend_lines_all_zero(self):
        out = tw.trend_lines([(self.D(2026, 10, 1), 0.0)])
        self.assertNotIn("busiest", "\n".join(out))


class DailyCli(CliRunner, unittest.TestCase):
    def test_daily_json_has_requested_days(self):
        d = json.loads(self.run_cli("--daily", "--json", "--since", "2026-10-01", "--until", "2026-10-03"))
        self.assertEqual(len(d["days"]), 3)
        self.assertAlmostEqual(d["total_cost"], 0.01)
        self.assertEqual(d["days"][0]["date"], "2026-10-01")

    def test_daily_text_has_sparkline(self):
        self.assertIn("📈", self.run_cli("--daily", "--since", "2026-10-01", "--until", "2026-10-03"))

    def test_inverted_range_exits(self):
        with self.assertRaises(SystemExit):
            self.run_cli("--daily", "--since", "2026-10-05", "--until", "2026-10-01")


if __name__ == "__main__":
    unittest.main()
