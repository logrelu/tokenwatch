"""Option checking (twlib.args): typos are rejected, valid use is untouched."""
import os
import re
import subprocess
import sys
import unittest

from tests.helpers import ROOT
from twlib import args


def problem(*tokens):
    return args.find_problem(list(tokens))


class FindProblem(unittest.TestCase):
    def test_valid_combinations_pass(self):
        for tokens in ([], ["--week"], ["--daily", "--week", "--project", "app"], ["--json", "--sessions", "3"],
                       ["--since", "2026-10-01", "--until", "2026-10-03"], ["--budget", "25", "--period", "week"],
                       ["--export", "html"], ["--export", "html", "/tmp/x.html", "--week"],
                       ["--export", "html", "--week"]):
            self.assertIsNone(args.find_problem(tokens), tokens)

    def test_trailing_comma_gets_a_hint(self):          # the typo that started this
        self.assertEqual(problem("--week,"), "unknown option '--week,' (did you mean --week?)")

    def test_misspelling_gets_a_hint(self):
        self.assertIn("did you mean --budget?", problem("--budgt", "25"))
        self.assertIn("did you mean --week?", problem("--wek"))

    def test_nonsense_option_has_no_hint(self):
        msg = problem("--zzzzzz")
        self.assertEqual(msg, "unknown option '--zzzzzz'")

    def test_equals_form_explains_the_fix(self):
        self.assertIn("--project foo", problem("--project=foo"))

    def test_stray_word_is_rejected(self):
        self.assertIn("unexpected argument 'stray'", problem("stray"))

    def test_value_options_need_a_value(self):
        self.assertEqual(problem("--project"), "--project needs a value")
        self.assertEqual(problem("--project", "--week"), "--project needs a value")
        self.assertEqual(problem("--budget"), "--budget needs a value")

    def test_negative_budget_is_left_to_the_budget_check(self):
        self.assertIsNone(problem("--budget", "-3"))      # parse_budget gives the friendlier message

    def test_export_needs_html(self):
        self.assertIn("--export needs 'html'", problem("--export"))
        self.assertIn("--export needs 'html'", problem("--export", "pdf"))


class Registry(unittest.TestCase):
    def test_every_flag_used_in_the_code_is_registered(self):
        """Guards against adding a flag to the code and forgetting FLAGS (it would then be rejected)."""
        used = set()
        for name in ("tokenwatch.py", "twlib/cli.py", "twlib/budget.py", "twlib/dates.py"):
            with open(os.path.join(ROOT, name), encoding="utf-8") as fh:
                used |= set(re.findall(r'"(--[a-z]+)"', fh.read()))
        self.assertLessEqual(used, set(args.FLAGS), sorted(used - set(args.FLAGS)))

    def test_usage_mentions_every_option(self):
        for flag in args.FLAGS:
            self.assertIn(flag, args.USAGE)


def run(*cli_args):
    return subprocess.run([sys.executable, os.path.join(ROOT, "tokenwatch.py"), *cli_args],
                          capture_output=True, text=True, env={**os.environ, "HOME": "/nonexistent"})


class CommandLine(unittest.TestCase):
    def test_typo_exits_2_on_stderr_and_prints_no_report(self):
        r = run("--week,")
        self.assertEqual(r.returncode, 2)
        self.assertEqual(r.stdout, "")
        self.assertIn("did you mean --week?", r.stderr)
        self.assertIn("--help", r.stderr)

    def test_help_exits_0(self):
        r = run("--help")
        self.assertEqual(r.returncode, 0)
        self.assertIn("usage:", r.stdout)
        self.assertEqual(run("-h").stdout, r.stdout)

    def test_valid_run_still_works(self):
        self.assertEqual(run("--week", "--json").returncode, 0)

    def test_readme_error_sample_is_the_real_output(self):
        """The README shows this error; it must stay identical to what the tool prints."""
        first_line = run("--week,").stderr.splitlines()[0]
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            self.assertIn(first_line, fh.read())


if __name__ == "__main__":
    unittest.main()
