"""Date filters (twlib.dates, twlib.scan.scan_project)."""
import json, os, shutil, tempfile
import unittest

from tests.helpers import tw, reply


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


if __name__ == "__main__":
    unittest.main()
