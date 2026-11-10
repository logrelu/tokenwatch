#!/usr/bin/env python3
"""Builds a FAKE ~/.claude/projects tree and renders the README examples from it with the real CLI.

All data here is invented (project "myapp", model usage, dates in Oct 2026); nothing is read from your
machine. Output is deterministic (UTC, fixed dates), so it can be checked in CI.

    python3 examples/demo.py                 # print every example block
    python3 examples/demo.py --update-readme # rewrite the <!-- demo:NAME --> blocks in README.md
    python3 examples/demo.py --dashboard     # rewrite both sample dashboards in examples/
    python3 examples/demo.py --check         # exit 1 if README.md or the sample dashboard is out of date
"""
import contextlib, io, json, os, re, shutil, sys, tempfile, time
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["TZ"] = "UTC"
time.tzset()

import tokenwatch as tw
from twlib import cli, config, dashboard, recap, scan

README = os.path.join(ROOT, "README.md")
SAMPLE = os.path.join(ROOT, "examples", "dashboard-sample.html")
WEATHER = os.path.join(ROOT, "examples", "dashboard-sample-weather.html")
OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"
BLOCKS = ("session", "report", "daily", "budget", "recap")


def _ts(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _turn(mid, t, model, inp, out, write, read, tool=None):
    content = [{"type": "tool_use", "name": tool, "input": {}}] if tool else []
    return {"timestamp": _ts(t), "message": {"id": mid, "model": model, "content": content, "usage": {
        "input_tokens": inp, "output_tokens": out,
        "cache_creation_input_tokens": write, "cache_read_input_tokens": read}}}


def _hook(t, n):
    return {"timestamp": _ts(t), "attachment": {
        "type": "hook_success", "command": "python3 ${CLAUDE_PLUGIN_ROOT}/check.py",
        "durationMs": 1100, "content": "[some-plugin] ok " + "x" * 12 + str(n)}}


def long_session():
    """1 Oct: a 120-turn Opus chat that grows to ~210K tokens, restarts cold twice, with chatty hooks."""
    out, t, ctx = [], datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc), 51_000
    cold_at = {45, 90}
    for i in range(120):
        t += timedelta(hours=2) if i in cold_at else timedelta(minutes=3)
        if i == 0:
            out.append(_turn("a0", t, OPUS, 6, 700, ctx, 0))
        elif i in cold_at:
            out.append(_turn(f"a{i}", t, OPUS, 6, 350, ctx, 0))           # saved copy expired: all re-written
        else:
            ctx = min(210_000, ctx + 4_000)
            out.append(_turn(f"a{i}", t, OPUS, 6, 350, 4_000, ctx - 4_000,
                             tool="mcp__some-server__query" if i % 20 == 5 else None))
        for k in range(4):
            out.append(_hook(t, i * 4 + k))
    return out


def short_session():
    """2 Oct: a short Opus session that a cheaper model could have done."""
    out, t = [], datetime(2026, 10, 2, 9, 30, tzinfo=timezone.utc)
    for i in range(20):
        t += timedelta(minutes=4)
        out.append(_turn(f"b{i}", t, OPUS, 5, 13_500, 2_500, 18_000 + i * 2_500,
                         tool="mcp__some-server__query" if i % 4 == 1 else None))
    return out


def short_agent():
    """2 Oct: a Haiku helper the short session started to search the code (saved in short/subagents/)."""
    out, t = [], datetime(2026, 10, 2, 9, 40, tzinfo=timezone.utc)
    for i in range(8):
        t += timedelta(minutes=1)
        out.append(_turn(f"s{i}", t, HAIKU, 4, 900, 3_000, 9_000 + i * 3_000))
    return out


def lean_session():
    """3 Oct: a small, healthy Sonnet session in another project."""
    out, t = [], datetime(2026, 10, 3, 14, 0, tzinfo=timezone.utc)
    for i in range(30):
        t += timedelta(minutes=2)
        out.append(_turn(f"c{i}", t, SONNET, 4, 600, 900, 6_000 + i * 900))
    return out


def build(root):
    """Write the fake projects under `root`."""
    for proj, sessions in {"-Users-demo-Desktop-myapp": {"long": long_session(), "short": short_session()},
                           "-Users-demo-Documents-blog": {"lean": lean_session()}}.items():
        os.makedirs(os.path.join(root, proj))
        for name, lines in sessions.items():
            with open(os.path.join(root, proj, name + ".jsonl"), "w") as fh:
                fh.write("\n".join(json.dumps(d) for d in lines) + "\n")
    sub = os.path.join(root, "-Users-demo-Desktop-myapp", "short", "subagents")
    os.makedirs(sub)
    with open(os.path.join(sub, "agent-demo1.jsonl"), "w") as fh:
        fh.write("\n".join(json.dumps(dict(d, isSidechain=True)) for d in short_agent()) + "\n")


def run(*args):
    """Run the real CLI against the fake projects and return its stdout."""
    root = tempfile.mkdtemp()
    saved = (config.PROJECTS, scan.HOME, cli.period_range, sys.argv, config.PREFS, os.environ.pop("TOKENWATCH_BUDGET", None),
             recap.today_fn)
    try:
        build(root)
        config.PROJECTS, scan.HOME = root, "/Users/demo"
        config.PREFS = os.path.join(root, "no-saved-settings.json")   # your saved budget/theme never leak in
        recap.today_fn = lambda: date(2026, 10, 5)                     # a Monday: "last week" holds the demo data
        cli.period_range = lambda period, today=None: (date(2026, 10, 1), date(2026, 10, 7))
        sys.argv = ["tokenwatch.py", *args]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tw.main()
        return buf.getvalue()
    finally:
        config.PROJECTS, scan.HOME, cli.period_range, sys.argv, config.PREFS, env, recap.today_fn = saved
        if env is not None: os.environ["TOKENWATCH_BUDGET"] = env
        shutil.rmtree(root)


def dashboard_html(theme="classic"):
    """The dashboard for the fake projects: a fixed week, a $25 weekly budget, and a fixed 'today'."""
    root = tempfile.mkdtemp()
    saved = (config.PROJECTS, scan.HOME)
    try:
        build(root)
        config.PROJECTS, scan.HOME = root, "/Users/demo"
        data = dashboard.collect(None, date(2026, 10, 1), date(2026, 10, 7), (25.0, "week"), today=date(2026, 10, 7))
        return dashboard.render_theme(data, theme)
    finally:
        config.PROJECTS, scan.HOME = saved
        shutil.rmtree(root)


def blocks():
    report = run("--project", "myapp").strip("\n")
    session, grab = [], False
    for line in report.split("\n"):                  # the 1 Oct session, dedented, as in "Example"
        if line.startswith("   ▸ 1 Oct"): grab = True
        elif grab and line.startswith("   ▸"): break
        elif grab and line.startswith("🤖"): break
        if grab: session.append(line[3:])
    daily = run("--daily", "--since", "2026-10-01", "--until", "2026-10-07").strip("\n")
    daily = "\n".join(daily.split("\n")[:-2])         # drop the totals footer; the table is the example
    budget = [l for l in run("--budget", "25", "--period", "week", "--sessions", "0").split("\n") if l.startswith("💰")][0]
    return {"session": "\n".join(session).strip("\n"), "report": report, "daily": daily, "budget": budget,
            "recap": run("--recap").strip("\n")}


def render(text, data):
    """Replace the fenced block inside every <!-- demo:NAME --> ... <!-- /demo:NAME --> pair."""
    for name in BLOCKS:
        pat = re.compile(r"(<!-- demo:%s -->\n)```\n.*?\n```(\n<!-- /demo:%s -->)" % (name, name), re.S)
        if not pat.search(text): raise SystemExit(f"README.md is missing the demo:{name} markers")
        text = pat.sub(lambda m: f"{m.group(1)}```\n{data[name]}\n```{m.group(2)}", text)
    return text


if __name__ == "__main__":
    if "--dashboard" in sys.argv:
        for path, theme in ((SAMPLE, "classic"), (WEATHER, "weather")):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(dashboard_html(theme))
            print("examples/%s written (made-up data)" % os.path.basename(path))
        sys.exit(0)
    data = blocks()
    if "--update-readme" in sys.argv or "--check" in sys.argv:
        old = open(README).read()
        new = render(old, data)
        if "--check" in sys.argv:
            try:
                sample_ok = all(open(p, encoding="utf-8").read() == dashboard_html(th)
                                for p, th in ((SAMPLE, "classic"), (WEATHER, "weather")))
            except OSError: sample_ok = False
            if new != old:
                sys.exit("README.md examples are out of date: run python3 examples/demo.py --update-readme")
            if not sample_ok:
                sys.exit("a sample dashboard in examples/ is out of date: run python3 examples/demo.py --dashboard")
            print("README examples and sample dashboard are up to date")
        else:
            open(README, "w").write(new)
            print("README.md examples updated")
    else:
        for name in BLOCKS: print(f"--- {name}\n{data[name]}\n")
