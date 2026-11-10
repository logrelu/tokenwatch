"""The per-file scan cache: hits, misses on any change, persistence, safety. Synthetic transcripts only;
config.CACHE always points into a temp folder."""
import json, os, shutil, stat, subprocess, sys, tempfile, unittest
from collections import defaultdict
from datetime import date
from unittest import mock

from tests.helpers import ROOT, reply
from twlib import cache, config, scan


def write(path, *replies):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as fh:
        for r in replies: fh.write(json.dumps(r) + "\n")
    return path


class CacheCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        saved = config.CACHE
        self.addCleanup(lambda: (setattr(config, "CACHE", saved), cache.reset()))
        config.CACHE = os.path.join(self.tmp, "cache", "scan.json")
        cache.reset()
        self.f = write(os.path.join(self.tmp, "p", "s1.jsonl"),
                       reply("a", output_tokens=1000, cache_read_input_tokens=5000),
                       {"timestamp": "2026-10-01T10:01:00Z", "message": {"id": "b", "model": "claude-opus-5-5",
                        "usage": {"output_tokens": 10}, "content": [
                            {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                            {"type": "tool_use", "name": "mcp__srv__q", "input": {}}]}})

    def scans(self):
        """Patch the real reader to count how often a transcript is actually read."""
        real = scan._scan_uncached
        calls = []
        p = mock.patch.object(scan, "_scan_uncached", side_effect=lambda f: calls.append(f) or real(f))
        p.start(); self.addCleanup(p.stop)
        return calls


class Hits(CacheCase):
    def test_second_scan_is_served_from_cache(self):
        calls = self.scans()
        first = scan.scan_session(self.f)
        again = scan.scan_session(self.f)
        self.assertEqual(len(calls), 1)
        self.assertEqual(again, first)

    def test_round_trip_keeps_types(self):
        s = scan._scan_uncached(self.f)
        back = cache.decode(json.loads(json.dumps(cache.encode(s))))
        self.assertEqual(back, s)
        self.assertIsInstance(back["plugins"], set)
        self.assertIsInstance(back["mcp"], defaultdict)
        self.assertEqual(back["mcp"]["unseen"], 0)                  # still a defaultdict(int)
        self.assertEqual(list(back["daily"]), [date(2026, 10, 1)])
        self.assertEqual(back["bash"], ["ls"])

    def test_hits_are_independent_copies(self):
        scan.scan_session(self.f)
        a = scan.scan_session(self.f); a["tokens"]["output_tokens"] = -1; a["bash"].append("x")
        b = scan.scan_session(self.f)
        self.assertEqual(b["tokens"]["output_tokens"], 1010)
        self.assertEqual(b["bash"], ["ls"])

    def test_changing_the_first_result_does_not_change_the_cache(self):
        first = scan.scan_session(self.f)
        first["tokens"]["output_tokens"] = -1; first["bash"].append("x"); first["mcp"]["new"] += 1
        again = scan.scan_session(self.f)
        self.assertEqual((again["tokens"]["output_tokens"], again["bash"], dict(again["mcp"])), (1010, ["ls"], {"srv": 1}))

    def test_survives_a_new_process(self):
        first = scan.scan_session(self.f)
        cache.save(); cache.reset()
        calls = self.scans()
        self.assertEqual(scan.scan_session(self.f), first)
        self.assertEqual(calls, [])


class Misses(CacheCase):
    def test_appended_transcript_is_read_again(self):
        calls = self.scans()
        before = scan.scan_session(self.f)["cost"]
        write(self.f, reply("c", output_tokens=5000))
        self.assertGreater(scan.scan_session(self.f)["cost"], before)
        self.assertEqual(len(calls), 2)

    def test_same_size_rewrite_is_read_again(self):
        calls = self.scans()
        scan.scan_session(self.f)
        st = os.stat(self.f)
        os.utime(self.f, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        scan.scan_session(self.f)
        self.assertEqual(len(calls), 2)

    def test_new_or_changed_subagent_is_read_again(self):
        calls = self.scans()
        scan.scan_session(self.f)
        agent = write(os.path.join(self.tmp, "p", "s1", "subagents", "agent-1.jsonl"), reply("x", output_tokens=100))
        self.assertEqual(scan.scan_session(self.f)["agents"], 1)
        write(agent, reply("y", output_tokens=100))
        self.assertEqual(scan.scan_session(self.f)["agent_turns"], 2)
        os.remove(agent)
        self.assertEqual(scan.scan_session(self.f)["agents"], 0)
        self.assertEqual(len(calls), 4)

    def test_price_or_version_change_discards_everything(self):
        scan.scan_session(self.f); cache.save(); cache.reset()
        calls = self.scans()
        with mock.patch.object(cache, "STAMP", "other"):
            scan.scan_session(self.f)
        self.assertEqual(len(calls), 1)

    def test_stamp_follows_prices_and_version(self):
        from twlib import pricing
        doubled = [(m, (p[0] * 2,) + p[1:]) for m, p in pricing.PRICES]
        self.assertEqual(cache.make_stamp(), cache.STAMP)
        self.assertNotEqual(cache.make_stamp(prices=doubled), cache.STAMP)
        self.assertNotEqual(cache.make_stamp(cheaper="claude-haiku-5-5"), cache.STAMP)
        self.assertNotEqual(cache.make_stamp(version=cache.VERSION + 1), cache.STAMP)


class Safety(CacheCase):
    def test_file_and_folder_are_private(self):
        scan.scan_session(self.f); cache.save()
        self.assertEqual(stat.S_IMODE(os.stat(config.CACHE).st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(config.CACHE)).st_mode), 0o700)
        self.assertEqual([n for n in os.listdir(os.path.dirname(config.CACHE))], ["scan.json"])  # no temp left

    def test_corrupt_cache_means_a_full_scan_then_a_good_file(self):
        os.makedirs(os.path.dirname(config.CACHE))
        with open(config.CACHE, "w") as fh: fh.write("{not json")
        calls = self.scans()
        scan.scan_session(self.f)
        self.assertEqual(len(calls), 1)
        cache.save()
        self.assertEqual(json.load(open(config.CACHE))["stamp"], cache.STAMP)

    def test_bad_entry_is_ignored(self):
        os.makedirs(os.path.dirname(config.CACHE))
        sig = cache.signature([self.f])
        with open(config.CACHE, "w") as fh:
            json.dump({"stamp": cache.STAMP, "entries": {self.f: {"sig": sig, "s": {"oops": 1}}}}, fh)
        self.assertEqual(scan.scan_session(self.f)["tokens"]["output_tokens"], 1010)

    def test_off_writes_nothing(self):
        config.CACHE = None; cache.reset()
        calls = self.scans()
        scan.scan_session(self.f); scan.scan_session(self.f); cache.save()
        self.assertEqual(len(calls), 2)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "cache")))

    def test_symlinked_folder_is_not_written(self):
        elsewhere = os.path.join(self.tmp, "elsewhere"); os.makedirs(elsewhere)
        os.symlink(elsewhere, os.path.join(self.tmp, "cache"))
        scan.scan_session(self.f); cache.save()                     # must not raise
        self.assertEqual(os.listdir(elsewhere), [])

    def test_unwritable_location_does_not_raise(self):
        config.CACHE = "/nonexistent/tokenwatch/scan.json"; cache.reset()
        scan.scan_session(self.f); cache.save()

    def test_deleted_transcripts_are_dropped(self):
        other = write(os.path.join(self.tmp, "p", "s2.jsonl"), reply("z", output_tokens=1))
        scan.scan_session(self.f); scan.scan_session(other)
        os.remove(other); cache.save()
        self.assertEqual(list(json.load(open(config.CACHE))["entries"]), [self.f])

    def test_env_off_switch(self):
        code = "from twlib import config; print(config.CACHE)"
        for value, expect_none in (("off", True), ("0", True), ("", False)):
            env = dict(os.environ, TOKENWATCH_CACHE=value)
            out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True).stdout
            self.assertEqual(out.strip() == "None", expect_none, value)


class RealCli(unittest.TestCase):
    """tokenwatch.py run twice as a real process: same output, and the second run reads no transcript."""

    def test_two_runs(self):
        home = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, home)
        write(os.path.join(home, ".claude", "projects", "-Users-me-app", "s1.jsonl"), reply("a", output_tokens=1000))
        env = {k: v for k, v in os.environ.items() if k not in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "TOKENWATCH_CACHE",
                                                                "TOKENWATCH_BUDGET", "XDG_STATE_HOME")}
        env.update(HOME=home, PYTHONIOENCODING="utf-8")
        run = lambda: subprocess.run([sys.executable, os.path.join(ROOT, "tokenwatch.py"), "--json"], env=env,
                                     capture_output=True, text=True, timeout=30)
        first = run()
        path = os.path.join(home, ".cache", "tokenwatch", "scan.json")
        self.assertTrue(os.path.exists(path), first.stderr)
        before = os.stat(path).st_mtime_ns
        second = run()
        self.assertEqual(json.loads(second.stdout), json.loads(first.stdout))
        self.assertEqual(os.stat(path).st_mtime_ns, before)          # nothing changed, so nothing rewritten


if __name__ == "__main__":
    unittest.main()
