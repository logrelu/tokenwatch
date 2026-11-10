"""The README examples are generated from made-up data by examples/demo.py and must stay in sync."""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(ROOT, "examples", "demo.py")


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


if __name__ == "__main__":
    unittest.main()
