"""Reply usage parsing (twlib.usage)."""
import unittest

from tests.helpers import tw


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


if __name__ == "__main__":
    unittest.main()
