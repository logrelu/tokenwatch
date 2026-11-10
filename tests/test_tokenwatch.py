import contextlib, io, json, os, shutil, sys, tempfile, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenwatch as tw


def reply(mid, model="claude-sonnet-5-5", ts="2026-10-01T10:00:00Z", **usage):
    u = {"input_tokens": 0, "output_tokens": 0, "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    u.update(usage)
    return {"timestamp": ts, "message": {"id": mid, "model": model, "usage": u, "content": []}}


def write_session(lines):
    f = tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False)
    for d in lines:
        f.write((d if isinstance(d, str) else json.dumps(d)) + "\n")
    f.close()
    return f.name


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


class JsonOutput(unittest.TestCase):
    def run_cli(self, *args):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        pdir = os.path.join(root, "-Users-me-app")
        os.makedirs(pdir)
        with open(os.path.join(pdir, "s1.jsonl"), "w") as fh:
            fh.write(json.dumps(reply("a", output_tokens=1000)) + "\n")
        old_projects, old_argv = tw.PROJECTS, sys.argv
        tw.PROJECTS, sys.argv = root, ["tokenwatch.py", *args]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                tw.main()
        finally:
            tw.PROJECTS, sys.argv = old_projects, old_argv
        return out.getvalue()

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
