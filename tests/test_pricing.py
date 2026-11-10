"""Cost and pricing (twlib.pricing)."""
import unittest

from tests.helpers import tw


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


if __name__ == "__main__":
    unittest.main()
