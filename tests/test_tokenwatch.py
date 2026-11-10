import contextlib, io, json, os, shutil, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenwatch as tw


def reply(mid, model="claude-sonnet-5-5", ts="2026-10-01T10:00:00Z", **usage):
    u = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    u.update(usage)
    return {"timestamp": ts, "message": {"id": mid, "model": model, "usage": u, "content": []}}


def write_session(lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for d in lines:
        f.write((d if isinstance(d, str) else json.dumps(d)) + "\n")
    f.close()
    return f.name


class Formatting(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(tw.fmt(999), "999")
        self.assertEqual(tw.fmt(1500), "2K")
        self.assertEqual(tw.fmt(8_000_000), "8M")

    def test_money(self):
        self.assertEqual(tw.money(1.234), "$1.23")
        self.assertEqual(tw.money(1234.5), "$1,234")

    def test_nice(self):
        self.assertEqual(tw.nice("claude-fable-5-1"), "Fable 5.1")
        self.assertEqual(tw.nice(""), "?")

    def test_when_bad_input(self):
        self.assertEqual(tw.when("not a date"), "?")


class Cost(unittest.TestCase):
    def test_known_model(self):
        # sonnet-5: $2/M in, $10/M out
        c = tw.cost_of("claude-sonnet-5-5", {"input_tokens": 1_000_000, "output_tokens": 1_000_000})
        self.assertAlmostEqual(c, 12.0)

    def test_unknown_model_is_free(self):
        self.assertEqual(tw.cost_of("gpt-x", {"input_tokens": 10**6}), 0.0)

    def test_cache_write_5m_vs_1h(self):
        five = tw.cost_parts("claude-sonnet-5-5", {"cache_creation_input_tokens": 1_000_000})["write"]
        one = tw.cost_parts("claude-sonnet-5-5", {"cache_creation_input_tokens": 1_000_000,
                            "cache_creation": {"ephemeral_1h_input_tokens": 1_000_000}})["write"]
        self.assertAlmostEqual(five, 2.0 * tw.WRITE_5M)
        self.assertAlmostEqual(one, 2.0 * tw.WRITE_1H)

    def test_most_specific_prefix_wins(self):
        a = tw.cost_of("claude-opus-5-5", {"input_tokens": 10**6})
        b = tw.cost_of("claude-opus-4", {"input_tokens": 10**6})
        self.assertNotEqual(a, b)


class Usage(unittest.TestCase):
    def test_counts_each_reply_once(self):
        seen = []
        msg = {"id": "m1", "usage": {"output_tokens": 5}}
        self.assertIsNotNone(tw.new_usage(msg, seen))
        self.assertIsNone(tw.new_usage(msg, seen))

    def test_no_usage(self):
        self.assertIsNone(tw.new_usage({"id": "m"}, []))

    def test_context_of(self):
        self.assertEqual(tw.context_of({"input_tokens": 1, "cache_creation_input_tokens": 2,
                                        "cache_read_input_tokens": 3}), 6)


class ScanSession(unittest.TestCase):
    def test_totals_and_dedupe(self):
        f = write_session([reply("a", output_tokens=1000), reply("a", output_tokens=1000),
                           reply("b", output_tokens=1000), "not json"])
        self.addCleanup(os.unlink, f)
        s = tw.scan_session(f)
        self.assertEqual(s["turns"], 2)
        self.assertEqual(s["tokens"]["output_tokens"], 2000)
        self.assertEqual(s["start"], "2026-10-01T10:00:00Z")
        self.assertEqual(s["model"], "claude-sonnet-5-5")

    def test_empty_session(self):
        f = write_session([])
        self.addCleanup(os.unlink, f)
        self.assertEqual(tw.scan_session(f)["turns"], 0)

    def test_long_chat_tip(self):
        lines = [reply(f"m{i}", model="claude-opus-5-5", cache_read_input_tokens=200_000, output_tokens=10)
                 for i in range(60)]
        f = write_session(lines)
        self.addCleanup(os.unlink, f)
        tips = tw.session_tips(tw.scan_session(f))
        self.assertTrue(any(t.startswith("long chat") for t in tips))

    def test_cheap_session_has_no_tips(self):
        f = write_session([reply("a", output_tokens=10)])
        self.addCleanup(os.unlink, f)
        self.assertEqual(tw.session_tips(tw.scan_session(f)), [])


class JsonOutput(unittest.TestCase):
    def run_cli(self, *args):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        pdir = os.path.join(root, "-Users-me-app")
        os.makedirs(pdir)
        with open(os.path.join(pdir, "s1.jsonl"), "w") as fh:
            fh.write(json.dumps(reply("a", output_tokens=1000)) + "\n")
        old_projects, old_argv = tw.PROJECTS, sys.argv
        tw.PROJECTS, sys.argv = root, ["tokenwatch.py", *args]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                tw.main()
        finally:
            tw.PROJECTS, sys.argv = old_projects, old_argv
        return out.getvalue()

    def test_json_is_valid_and_complete(self):
        d = json.loads(self.run_cli("--json"))
        self.assertEqual(len(d["projects"]), 1)
        sess = d["projects"][0]["sessions"][0]
        self.assertEqual(sess["id"], "s1")
        self.assertEqual(sess["turns"], 1)
        self.assertEqual(sess["tokens"]["output_tokens"], 1000)
        self.assertAlmostEqual(d["total_cost"], 0.01)

    def test_text_report_unchanged_without_flag(self):
        out = self.run_cli()
        self.assertIn("all projects", out)
        with self.assertRaises(ValueError):
            json.loads(out)


class DateFilters(unittest.TestCase):
    TODAY = __import__("datetime").date(2026, 11, 9)

    def test_no_flags_is_open_ended(self):
        self.assertEqual(tw.date_range([], self.TODAY), (None, None))

    def test_today(self):
        self.assertEqual(tw.date_range(["--today"], self.TODAY), (self.TODAY, self.TODAY))

    def test_week_is_last_seven_days_inclusive(self):
        since, until = tw.date_range(["--week"], self.TODAY)
        self.assertEqual((until - since).days, 6)
        self.assertEqual(until, self.TODAY)

    def test_since_until(self):
        d = tw.date_range(["--since", "2026-10-01", "--until", "2026-10-31"], self.TODAY)
        self.assertEqual((d[0].isoformat(), d[1].isoformat()), ("2026-10-01", "2026-10-31"))

    def test_bad_date_raises(self):
        with self.assertRaises(ValueError):
            tw.date_range(["--since", "nope"], self.TODAY)

    def test_scan_project_filters_by_start_date(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        for name, ts in (("old", "2026-01-15T12:00:00Z"), ("new", "2026-10-15T12:00:00Z")):
            with open(os.path.join(root, name + ".jsonl"), "w") as fh:
                fh.write(json.dumps(reply(name, ts=ts, output_tokens=100)) + "\n")
        D = __import__("datetime").date
        self.assertEqual(tw.scan_project(root)["turns"], 2)
        self.assertEqual(tw.scan_project(root, since=D(2026, 10, 1))["turns"], 1)
        self.assertEqual(tw.scan_project(root, until=D(2026, 2, 1))["turns"], 1)
        self.assertEqual(tw.scan_project(root, since=D(2027, 1, 1))["turns"], 0)


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


class BudgetCli(JsonOutput):
    def test_budget_in_json_and_text(self):
        out = json.loads(self.run_cli("--json", "--budget", "100", "--period", "month"))
        self.assertIn(out["budget"]["level"], ("ok", "warn", "over"))
        self.assertIn("budget", self.run_cli("--budget", "100", "--period", "month"))

    def test_no_budget_key_value_is_null(self):
        old = os.environ.pop("TOKENWATCH_BUDGET", None)
        try: self.assertIsNone(json.loads(self.run_cli("--json"))["budget"])
        finally:
            if old: os.environ["TOKENWATCH_BUDGET"] = old


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


class DailyCli(JsonOutput):
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
