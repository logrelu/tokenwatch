"""The statusline's budget meter: cached live total, short coloured segment, and the real statusline.py.
Synthetic transcripts only; config paths point at temp folders."""
import json, os, shutil, subprocess, sys, tempfile, time, unittest
from datetime import date, datetime, timedelta, timezone

from tests.helpers import ROOT, reply
from twlib import config, prefs
from twlib.budget import budget_segment, budget_status, live_budget

TODAY = date.today()


def write_reply(root, project, session, day, out_tokens, mtime=None):
    """One Sonnet reply at local noon on `day`, costing $10 per 1M output tokens."""
    pdir = os.path.join(root, project)
    os.makedirs(pdir, exist_ok=True)
    path = os.path.join(pdir, session + ".jsonl")
    ts = (datetime.combine(day, datetime.min.time()).replace(hour=12).astimezone()
          .astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    with open(path, "a") as fh:
        fh.write(json.dumps(reply(session + str(out_tokens), ts=ts, output_tokens=out_tokens)) + "\n")
    if mtime is not None: os.utime(path, (mtime, mtime))
    return path


class LiveCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        saved = (config.PROJECTS, config.OUT_DIR, config.PREFS)
        self.addCleanup(lambda: setattr(config, "PROJECTS", saved[0]) or setattr(config, "OUT_DIR", saved[1])
                        or setattr(config, "PREFS", saved[2]))
        config.PROJECTS = os.path.join(self.tmp, "projects")
        config.OUT_DIR = os.path.join(self.tmp, "out")
        config.PREFS = os.path.join(self.tmp, "prefs.json")
        os.makedirs(config.PROJECTS)


class Segment(unittest.TestCase):
    def test_levels_have_words_and_colours(self):
        ok, warn, over = (budget_segment(budget_status(s, 25, "week")) for s in (5, 21, 30))
        self.assertEqual(ok, "💰 20% of $25/week")
        self.assertEqual(warn, "\033[33m💰 84% of $25/week nearly there\033[0m")
        self.assertEqual(over, "\033[31m💰 120% of $25/week OVER\033[0m")

    def test_no_colour_and_ascii(self):
        self.assertEqual(budget_segment(budget_status(30, 2.5, "day"), color=False, utf=False), "budget 1200% of $2.5/day OVER")

    def test_no_budget_no_segment(self):
        self.assertEqual(budget_segment(None), "")


class Live(LiveCase):
    def test_none_without_a_budget(self):
        write_reply(config.PROJECTS, "-p", "s", TODAY, 1_000_000)
        self.assertIsNone(live_budget())

    def test_uses_saved_budget_and_counts_the_period(self):
        prefs.save({"budget": "30/week"})
        write_reply(config.PROJECTS, "-p", "a", TODAY, 1_000_000)                       # $10, this week
        write_reply(config.PROJECTS, "-p", "b", TODAY - timedelta(days=20), 1_000_000)  # outside the week
        b = live_budget(today=TODAY)
        self.assertAlmostEqual(b["spent"], 10.0)
        self.assertEqual((b["budget"], b["period"], b["level"]), (30.0, "week", "ok"))

    def test_cached_for_five_minutes_then_recomputed(self):
        prefs.save({"budget": "20/week"})
        write_reply(config.PROJECTS, "-p", "a", TODAY, 1_000_000)
        t = time.time()
        self.assertAlmostEqual(live_budget(now=t, today=TODAY)["spent"], 10.0)
        write_reply(config.PROJECTS, "-p", "a2", TODAY, 1_000_000)
        self.assertAlmostEqual(live_budget(now=t + 60, today=TODAY)["spent"], 10.0)      # cached
        self.assertAlmostEqual(live_budget(now=t + 301, today=TODAY)["spent"], 20.0)     # recomputed
        self.assertEqual(live_budget(now=t + 302, today=TODAY)["level"], "over")

    def test_new_budget_ignores_old_cache(self):
        prefs.save({"budget": "20/week"})
        write_reply(config.PROJECTS, "-p", "a", TODAY, 1_000_000)
        t = time.time()
        live_budget(now=t, today=TODAY)
        prefs.save({"budget": "10/day"})
        b = live_budget(now=t + 1, today=TODAY)
        self.assertEqual((b["budget"], b["period"]), (10.0, "day"))

    def test_skips_files_untouched_since_before_the_period(self):
        prefs.save({"budget": "20/day"})
        old = time.time() - 10 * 86400
        write_reply(config.PROJECTS, "-p", "stale", TODAY, 1_000_000, mtime=old)   # claims today but untouched for days
        self.assertAlmostEqual(live_budget(today=TODAY)["spent"], 0.0)

    def test_cache_lives_in_the_private_folder(self):
        prefs.save({"budget": "20/week"})
        live_budget()
        self.assertEqual(os.listdir(config.OUT_DIR), ["budget.json"])
        self.assertEqual(os.stat(config.OUT_DIR).st_mode & 0o777, 0o700)

    def test_never_raises(self):
        prefs.save({"budget": "20/week"})
        os.makedirs(os.path.dirname(config.OUT_DIR), exist_ok=True)
        os.symlink(self.tmp, config.OUT_DIR)               # refused folder
        self.assertIsNone(live_budget())


class Statusline(LiveCase):
    """Runs the real statusline.py with HOME, XDG_CONFIG_HOME and TMPDIR pointed at the temp folder."""

    def run_statusline(self, budget=None, color=True):
        home = os.path.join(self.tmp, "home")
        projects = os.path.join(home, ".claude", "projects")
        tp = write_reply(projects, "-Users-me-app", "s1", TODAY, 1_000_000)
        if budget:
            os.makedirs(os.path.join(home, ".config", "tokenwatch"), exist_ok=True)
            with open(os.path.join(home, ".config", "tokenwatch", "config.json"), "w") as fh:
                json.dump({"budget": budget}, fh)
        env = {k: v for k, v in os.environ.items() if k not in ("TOKENWATCH_BUDGET", "NO_COLOR", "XDG_CONFIG_HOME")}
        tmpdir = os.path.join(self.tmp, "t")
        os.makedirs(tmpdir, exist_ok=True)
        env.update(HOME=home, TMPDIR=tmpdir, COLUMNS="200", PYTHONIOENCODING="utf-8")
        if not color: env["NO_COLOR"] = "1"
        r = subprocess.run([sys.executable, os.path.join(ROOT, "statusline.py")], input=json.dumps(
            {"model": {"display_name": "Sonnet"}, "transcript_path": tp}), capture_output=True, text=True,
            env=env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.splitlines()[0]

    def test_no_budget_no_meter(self):
        self.assertNotIn("💰", self.run_statusline())

    def test_meter_turns_red_when_over(self):
        line = self.run_statusline("8/week")
        self.assertIn("\033[31m💰 125% of $8/week OVER\033[0m", line)

    def test_no_color_respected(self):
        line = self.run_statusline("8/week", color=False)
        self.assertIn("💰 125% of $8/week OVER", line)
        self.assertNotIn("\033[31m", line)


if __name__ == "__main__":
    unittest.main()
