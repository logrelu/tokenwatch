"""The weather-report theme (twlib.weather): the joke mappings, the page, and --theme on the CLI."""
import os
import re
import subprocess
import sys
import tempfile
import unittest

from tests.helpers import ROOT
from twlib import dashboard, weather


def data(**over):
    """A minimal dashboard.collect()-shaped dict."""
    d = {
        "generated": "2026-10-07", "filter": {"project": "", "since": "", "until": ""}, "mood": "😺",
        "totals": {"cost": 12.0, "tokens": 5_000_000, "sessions": 2, "turns": 40},
        "daily": [{"date": "2026-10-01", "cost": 10.0}, {"date": "2026-10-02", "cost": 2.0}, {"date": "2026-10-03", "cost": 0.0}],
        "budget": {"period": "week", "budget": 25.0, "spent": 12.0, "used": 0.48, "level": "ok"}, "budget_pace": 3.57,
        "projects": [{"name": "~/Desktop/myapp", "cost": 12.0}],
        "spent": {"read": 6.0, "write": 3.0, "out": 3.0, "in": 0.0},
        "sessions": [{"date": "2026-10-01", "project": "~/Desktop/myapp", "model": "Opus 5.5", "cost": 10.0, "turns": 30},
                     {"date": "2026-10-02", "project": "~/Desktop/myapp", "model": "Sonnet 5.5", "cost": 2.0, "turns": 10}],
        "tips": [{"project": "~/Desktop/myapp", "text": "long chat: 50% of the cost was re-reading."}],
    }
    d.update(over)
    return d


class Mappings(unittest.TestCase):
    def test_condition_scale(self):
        ref = 4.0
        self.assertEqual(weather.condition(0, ref), "clear")
        self.assertEqual(weather.condition(1.0, ref), "sunny")
        self.assertEqual(weather.condition(3.0, ref), "partly")
        self.assertEqual(weather.condition(5.0, ref), "rain")
        self.assertEqual(weather.condition(6.0, ref), "storm")
        self.assertEqual(weather.condition(5.0, 0), "sunny")          # no reference: never alarming

    def test_reference_is_pace_or_average_spending_day(self):
        days = [{"cost": 4.0}, {"cost": 0.0}, {"cost": 2.0}]
        self.assertEqual(weather.reference(days, 3.57), 3.57)
        self.assertEqual(weather.reference(days, None), 3.0)
        self.assertEqual(weather.reference([{"cost": 0.0}], None), 0.0)

    def test_advisories(self):
        self.assertEqual(weather.advisory("long chat: 43% ..."), "Flood Warning")
        self.assertEqual(weather.advisory("cold restarts: 2 times ..."), "Freeze Warning")
        self.assertEqual(weather.advisory("plugin hooks (x) ran ..."), "Wind Advisory")
        self.assertEqual(weather.advisory("model: this ran on Opus"), "Heat Advisory")
        self.assertEqual(weather.advisory("⚠ heavy session start: ~51K"), "Dense Fog Advisory")
        self.assertEqual(weather.advisory("something new"), "Special Weather Statement")

    def test_storm_category(self):
        self.assertEqual(weather.storm_category(10, 10), 5)
        self.assertEqual(weather.storm_category(0.1, 10), 1)
        self.assertEqual(weather.storm_category(5, 10), 3)
        self.assertEqual(weather.storm_category(3, 0), 1)

    def test_overall_follows_budget_level(self):
        for level, want in (("ok", "sunny"), ("warn", "rain"), ("over", "storm")):
            b = dict(data()["budget"], level=level)
            self.assertEqual(weather.overall(data(budget=b)), want)

    def test_overall_without_budget_is_the_worst_day(self):
        self.assertEqual(weather.overall(data(budget=None, budget_pace=None)), "storm")   # 10 vs avg 6 -> 1.67x

    def test_forecast_text(self):
        lines = weather.forecast_text(data())
        self.assertIn("Thu 1 Oct", " ".join(lines))
        self.assertIn("drizzle (re-reading history)", " ".join(lines))
        self.assertIn("steady at 48%", " ".join(lines))
        quiet = weather.forecast_text(data(totals={"cost": 0, "tokens": 0, "sessions": 0, "turns": 0}))
        self.assertEqual(len(quiet), 1)
        self.assertIn("not a token in sight", quiet[0])

    def test_proper_noun_keeps_its_capital(self):
        self.assertEqual(weather._lc("Claude's writing"), "Claude's writing")
        self.assertEqual(weather._lc("Re-reading history"), "re-reading history")


class Page(unittest.TestCase):
    def test_all_sections_present(self):
        page = weather.render(data())
        for heading in ("The Token Forecast", "Your forecast", "Barometer", "Radar", "Regional outlook",
                        "Storm tracker", "Weather advisories", "Flood Warning", "Storm Alberto"):
            self.assertIn(heading, page)
        self.assertEqual(page.count("Show as table"), 4)          # every chart has a table view

    def test_self_contained(self):
        page = weather.render(data())
        for needle in ("http://", "https://", "<script", "<link", "<img", "url("):
            self.assertNotIn(needle, page)

    def test_hostile_project_name_is_escaped(self):
        evil = "<script>alert(1)</script>"
        d = data(projects=[{"name": evil, "cost": 1.0}],
                 sessions=[{"date": "2026-10-01", "project": evil, "model": evil, "cost": 1.0, "turns": 1}],
                 tips=[{"project": evil, "text": evil}])
        page = weather.render(d)
        self.assertNotIn(evil, page)
        self.assertIn("&lt;script&gt;", page)

    def test_empty_data_renders(self):
        page = weather.render(data(totals={"cost": 0, "tokens": 0, "sessions": 0, "turns": 0}, daily=[], budget=None,
                                   budget_pace=None, projects=[], spent={"read": 0, "write": 0, "out": 0, "in": 0},
                                   sessions=[], tips=[]))
        for quiet in ("not a token in sight", "No regions reporting", "Quiet season", "No advisories", "No budget set"):
            self.assertIn(quiet, page)

    def test_render_theme_switch(self):
        self.assertIn("The Token Forecast", dashboard.render_theme(data(), "weather"))
        self.assertNotIn("The Token Forecast", dashboard.render_theme(data(), "classic"))


def run(*cli_args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "tokenwatch.py"), *cli_args],
                          capture_output=True, text=True, env={**os.environ, "HOME": "/nonexistent"})


class CommandLine(unittest.TestCase):
    def test_theme_weather_writes_the_forecast(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "f.html")
            r = run("--export", "html", path, "--theme", "weather")
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(path, encoding="utf-8") as fh:
                self.assertIn("The Token Forecast", fh.read())

    def test_unknown_theme_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            r = run("--export", "html", os.path.join(d, "f.html"), "--theme", "tornado")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("--theme must be one of: classic, weather", r.stderr)


if __name__ == "__main__":
    unittest.main()
