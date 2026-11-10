"""Tests for the static HTML dashboard (synthetic data only, never the real ~/.claude)."""
import contextlib, io, json, os, re, shutil, sys, tempfile, unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from twlib import config, dashboard
from twlib.cli import main

EVIL = "<script>alert(1)</script>"


def make_projects(names=("-Users-me-app",), model="claude-sonnet-5-5"):
    root = tempfile.mkdtemp()
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for name in names:
        pdir = os.path.join(root, name)
        os.makedirs(pdir)
        line = {"timestamp": ts, "message": {"id": "a", "model": model, "content": [],
                "usage": {"input_tokens": 100, "output_tokens": 5000,
                          "cache_creation_input_tokens": 1000, "cache_read_input_tokens": 20000}}}
        with open(os.path.join(pdir, "s1.jsonl"), "w") as fh:
            fh.write(json.dumps(line) + "\n")
    return root


class DashboardCase(unittest.TestCase):
    def projects(self, **kw):
        root = make_projects(**kw)
        self.addCleanup(shutil.rmtree, root)
        old = config.PROJECTS
        config.PROJECTS = root
        self.addCleanup(setattr, config, "PROJECTS", old)
        return root

    def page(self, budget=None, frag=None):
        return dashboard.render_html(dashboard.collect(frag=frag, budget=budget))

    def cli(self, *args):
        old = sys.argv
        sys.argv = ["tokenwatch.py", *args]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                main()
        finally:
            sys.argv = old
        return out.getvalue()


class Escaping(DashboardCase):
    def test_malicious_project_and_model_are_escaped(self):
        self.projects(names=("-Users-me-" + EVIL.replace("/", "-"),), model="claude-<b>x")
        page = self.page()
        self.assertNotIn("<script>alert(1)", page)
        self.assertNotIn("<b>", page)
        self.assertIn("&lt;script&gt;alert(1)", page)

    def test_embedded_json_cannot_close_its_script_tag(self):
        self.projects(names=("-Users-me-" + EVIL.replace("/", "-"),))
        blob = re.search(r'<script type="application/json" id="tw-data">(.*?)</script>', self.page(), re.S).group(1)
        self.assertNotIn("<", blob)
        data = json.loads(blob)
        self.assertEqual(data["totals"]["sessions"], 1)
        self.assertIn(EVIL.replace("/", "-")[:8], data["projects"][0]["name"])


class SelfContained(DashboardCase):
    def test_no_external_resources(self):
        self.projects()
        page = self.page(budget=(20.0, "week"))
        self.assertNotRegex(page, r"https?://")
        self.assertNotIn("<script src", page)
        self.assertNotIn("<link", page)
        self.assertNotIn("@import", page)
        self.assertNotIn("url(", page)

    def test_every_chart_has_a_table_view(self):
        self.projects()
        self.assertEqual(self.page().count("Show as table"), 3)


class Content(DashboardCase):
    def test_empty_data_still_renders(self):
        self.projects(names=())
        page = self.page()
        self.assertIn("<svg", page)
        self.assertIn("No usage found", page)
        self.assertIn("No sessions found", page)
        self.assertIn("Nothing to fix", page)

    def test_totals_and_split(self):
        self.projects()
        data = dashboard.collect()
        self.assertEqual(data["totals"]["sessions"], 1)
        self.assertEqual(data["totals"]["turns"], 1)
        self.assertAlmostEqual(sum(data["spent"].values()), data["totals"]["cost"], places=3)
        self.assertEqual(len(data["daily"]), 14)

    def test_budget_line_only_when_set(self):
        self.projects()
        self.assertNotIn('class="pace"', self.page())
        self.assertNotIn("Budget pace", self.page())
        with_budget = self.page(budget=(20.0, "week"))
        self.assertIn('class="pace"', with_budget)
        self.assertIn("Budget pace", with_budget)

    def test_project_filter(self):
        self.projects(names=("-Users-me-alpha", "-Users-me-beta"))
        data = dashboard.collect(frag="alpha")
        self.assertEqual(len(data["projects"]), 1)
        self.assertIn("alpha", data["projects"][0]["name"])

    def test_extra_projects_fold_into_other(self):
        self.projects(names=tuple("-Users-me-p%d" % i for i in range(11)))
        projects = dashboard.collect()["projects"]
        self.assertEqual(len(projects), dashboard.TOP_PROJECTS + 1)
        self.assertTrue(projects[-1].get("other"))


class Cli(DashboardCase):
    def test_writes_valid_file_to_path(self):
        self.projects()
        out_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, out_dir)
        path = os.path.join(out_dir, "d.html")
        said = self.cli("--export", "html", path)
        self.assertIn(path, said)
        self.assertIn("don't share it publicly", said)
        with open(path, encoding="utf-8") as fh:
            page = fh.read()
        self.assertTrue(page.startswith("<!doctype html>"))
        self.assertTrue(page.rstrip().endswith("</html>"))

    def test_bad_export_target_exits(self):
        self.projects()
        with self.assertRaises(SystemExit):
            self.cli("--export", "pdf")

    def test_since_after_until_exits(self):
        self.projects()
        with self.assertRaises(SystemExit):
            self.cli("--export", "html", os.devnull, "--since", "2026-10-02", "--until", "2026-10-01")


if __name__ == "__main__":
    unittest.main()
