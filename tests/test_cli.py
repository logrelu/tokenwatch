"""The --json report and unchanged text report."""
import json
import unittest

from tests.helpers import CliRunner


class JsonOutput(CliRunner, unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
