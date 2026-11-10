"""Scanning transcripts (twlib.scan) and per-session tips."""
import os
import unittest

from tests.helpers import tw, reply, write_session


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


if __name__ == "__main__":
    unittest.main()
