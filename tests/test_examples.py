"""The README examples are generated from made-up data by examples/demo.py and must stay in sync."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "demo.py")
SAMPLE = os.path.join(ROOT, "examples", "dashboard-sample.html")


def demo(*args):
    return subprocess.run([sys.executable, DEMO, *args], capture_output=True, text=True,
                          env={**os.environ, "HOME": "/nonexistent"})


class ReadmeExamples(unittest.TestCase):
    def test_readme_matches_generated_output(self):
        r = demo("--check")
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)

    def test_demo_output_has_no_real_machine_data(self):
        out = demo().stdout
        self.assertIn("~/Desktop/myapp", out)
        for real in (os.path.expanduser("~"), os.environ.get("USER", "\0")):
            self.assertNotIn(real, out)

    def test_demo_is_deterministic(self):
        self.assertEqual(demo().stdout, demo().stdout)


class SampleDashboard(unittest.TestCase):
    def setUp(self):
        with open(SAMPLE, encoding="utf-8") as fh:
            self.html = fh.read()

    def test_sample_is_in_sync_with_the_generator(self):
        r = demo("--check")                       # also compares the sample file with a fresh render
        self.assertEqual(r.returncode, 0, r.stderr or r.stdout)

    def test_sample_shows_only_made_up_data(self):
        import re
        self.assertIn("~/Desktop/myapp", self.html)
        self.assertEqual(re.findall(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", self.html), [])
        for real in (os.path.expanduser("~"), os.environ.get("USER", "\0"), "gmail"):
            self.assertNotIn(real, self.html)

    def test_sample_has_no_external_resources_and_no_real_paths(self):
        for needle in ("http://", "https://", "<script src", "<link"):
            self.assertNotIn(needle, self.html)
        import re
        self.assertEqual(sorted(set(re.findall(r"/Users/[\w./-]+", self.html))), [])
        self.assertEqual(sorted(set(re.findall(r"~/[\w./-]+", self.html))), ["~/Desktop/myapp", "~/Documents/blog"])


if __name__ == "__main__":
    unittest.main()
