"""Formatting helpers (twlib.fmt)."""
import unittest

from tests.helpers import tw


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


if __name__ == "__main__":
    unittest.main()
