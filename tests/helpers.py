"""Shared test helpers: synthetic transcripts and a CLI runner that never touches real data."""
import contextlib, io, json, os, shutil, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import tokenwatch as tw
from twlib import config


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


class CliRunner:
    """Mixin: run_cli(*args) runs tokenwatch against one synthetic project and returns stdout."""

    def run_cli(self, *args):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        pdir = os.path.join(root, "-Users-me-app")
        os.makedirs(pdir)
        with open(os.path.join(pdir, "s1.jsonl"), "w") as fh:
            fh.write(json.dumps(reply("a", output_tokens=1000)) + "\n")
        old_projects, old_argv = config.PROJECTS, sys.argv
        config.PROJECTS, sys.argv = root, ["tokenwatch.py", *args]
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                tw.main()
        finally:
            config.PROJECTS, sys.argv = old_projects, old_argv
        return out.getvalue()
