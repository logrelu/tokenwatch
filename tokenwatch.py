#!/usr/bin/env python3
"""tokenwatch — reads your local Claude Code transcripts and tells you where tokens go.

Everything is local: ~/.claude/projects/**/*.jsonl never leaves this machine.
Run: python3 tokenwatch.py [--project <name-fragment>] [--sessions <how many per project>] [--json]
     [--today | --week | --since YYYY-MM-DD [--until YYYY-MM-DD]] [--daily]
"""
import json, glob, os, re, sys
from collections import defaultdict
from datetime import datetime, date, timedelta
from twlib.fmt import fmt, money, nice, when
from twlib.usage import new_usage, context_of, PLUGIN_MARK, plugin_hook
from twlib.pricing import KINDS, PRICES, WRITE_5M, WRITE_1H, TOP_TIER, CHEAPER, cost_parts, cost_of
from twlib.live import new_live_state, ingest, update_rate, mood_of
from twlib.tips import top_tip, session_tips, advise

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")


def scan_session(f):
    """Everything tokenwatch knows about one session transcript."""
    s = dict(file=f, start="", turns=0, cost=0.0, tokens={k: 0 for k in KINDS},
             spent={"read": 0.0, "write": 0.0, "out": 0.0, "in": 0.0}, as_cheaper=0.0,
             peak=0, context=0, first_write=0, model="", rebuilds=0, rebuild_cost=0.0,
             hook_runs=0, hook_secs=0.0, hook_chars=0, plugins=set(), bash=[], mcp=defaultdict(int),
             daily=defaultdict(float))
    seen = []
    with open(f, errors="ignore") as fh:
        lines = fh.readlines()
    for line in lines:
        h = plugin_hook(line)
        if h:
            s["hook_runs"] += h[0]; s["hook_secs"] += h[1]; s["hook_chars"] += h[2]; s["plugins"].update(h[3])
            continue
        try: d = json.loads(line)
        except Exception: continue
        if not s["start"]: s["start"] = d.get("timestamp") or ""
        msg = d.get("message") or {}
        u = new_usage(msg, seen)
        if u:
            model = msg.get("model") or ""
            parts = cost_parts(model, u)
            s["turns"] += 1
            s["cost"] += sum(parts.values())
            s["as_cheaper"] += cost_of(CHEAPER, u)
            for k in parts: s["spent"][k] += parts[k]
            day = session_date(d.get("timestamp") or "")
            if day: s["daily"][day] += sum(parts.values())
            for k in KINDS: s["tokens"][k] += u.get(k, 0)
            if model.startswith("claude"): s["model"] = model
            s["context"] = context_of(u); s["peak"] = max(s["peak"], s["context"])
            w = u.get("cache_creation_input_tokens", 0)
            if s["turns"] == 1:
                s["first_write"] = w
            elif w > 50_000 and w > 0.5 * s["context"]:
                # most of the conversation written to cache again: the saved copy had expired
                s["rebuilds"] += 1; s["rebuild_cost"] += parts["write"]
        for c in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                name = c.get("name", "")
                if name.startswith("mcp__"):
                    s["mcp"][name.split("__")[1]] += 1
                elif name == "Bash":
                    s["bash"].append((c.get("input") or {}).get("command", "")[:200])
    return s


def session_date(start):
    """Local calendar date a session started on, or None if the timestamp is unreadable."""
    try: return datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone().date()
    except Exception: return None

def date_range(argv, today=None):
    """(since, until) dates from --since/--until/--today/--week, either may be None (open-ended).
    Raises ValueError on a bad date."""
    today = today or date.today()
    def val(flag):
        return date.fromisoformat(argv[argv.index(flag) + 1]) if flag in argv else None
    since, until = val("--since"), val("--until")
    if "--today" in argv: since = until = today
    if "--week" in argv: since, until = today - timedelta(days=6), today
    return since, until

PERIODS = ("day", "week", "month")

def period_range(period, today=None):
    """(first day, last day) of the budget period that contains today: today, the last 7 days,
    or the calendar month so far."""
    today = today or date.today()
    if period == "day": return today, today
    if period == "week": return today - timedelta(days=6), today
    return today.replace(day=1), today

def parse_budget(argv, env=None):
    """(amount, period) from `--budget 20 [--period week]` or TOKENWATCH_BUDGET=20/week, else None.
    Raises ValueError on a bad amount or period."""
    env = os.environ if env is None else env
    raw, period = None, "week"
    if "--budget" in argv:
        raw = argv[argv.index("--budget") + 1]
        if "--period" in argv: period = argv[argv.index("--period") + 1]
    elif env.get("TOKENWATCH_BUDGET"):
        raw, _, p = env["TOKENWATCH_BUDGET"].partition("/")
        period = p or period
    if raw is None: return None
    amount = float(raw)
    if amount <= 0 or period not in PERIODS: raise ValueError("bad budget")
    return amount, period

def spend_between(sessions, since, until):
    """Total cost of all replies dated within [since, until]."""
    return sum(c for x in sessions for d, c in x["daily"].items() if since <= d <= until)

def budget_status(spent, amount, period):
    return {"period": period, "budget": amount, "spent": round(spent, 4), "used": round(spent / amount, 4),
            "level": "over" if spent >= amount else "warn" if spent >= 0.8 * amount else "ok"}

def budget_line(b, width=10):
    filled = min(width, int(b["used"] * width))
    bar = "▓" * filled + "░" * (width - filled)
    mood = {"over": "🙀 over budget", "warn": "😿 nearly there", "ok": "😺 on track"}[b["level"]]
    where = {"day": "today", "week": "last 7 days", "month": "this month"}[b["period"]]
    return f"💰 {where}: {money(b['spent'])} of {money(b['budget'])} budget ({b['used']:.0%}) {bar} {mood}"

SPARK = "▁▂▃▄▅▆▇█"

def sparkline(values):
    """One block character per value, scaled to the largest (all-zero stays at the lowest block)."""
    top = max(values, default=0)
    if top <= 0: return SPARK[0] * len(values)
    return "".join(SPARK[int(v / top * (len(SPARK) - 1) + 0.5)] for v in values)

def daily_totals(sessions, since, until):
    """[(day, cost)] for every calendar day from since to until inclusive, zero-filled."""
    out, d = [], since
    while d <= until:
        out.append((d, sum(x["daily"].get(d, 0.0) for x in sessions)))
        d += timedelta(days=1)
    return out

def trend_lines(days):
    """Printable per-day table headed by a sparkline, busiest day marked."""
    top = max((c for _, c in days), default=0)
    lines = [f"📈 {sparkline([c for _, c in days])}  {days[0][0]:%d %b} → {days[-1][0]:%d %b}"]
    for d, c in days:
        bar = "█" * (int(c / top * 20 + 0.5) if top else 0)
        lines.append(f"   {d:%a %d %b}  {money(c):>8}  {bar}" + ("  🔥 busiest" if top and c == top else ""))
    return lines

def project_name(pdir):
    return os.path.basename(pdir).replace("-Users-" + os.path.basename(HOME) + "-", "~/").replace("-", "/")

def scan_project(pdir, since=None, until=None):
    sessions = [scan_session(f) for f in sorted(glob.glob(os.path.join(pdir, "*.jsonl")))]
    if since or until:
        def inside(x):
            d = session_date(x["start"])
            return d is not None and (not since or d >= since) and (not until or d <= until)
        sessions = [x for x in sessions if inside(x)]
    stats = {k: sum(s["tokens"][k] for s in sessions) for k in KINDS}
    mcp = defaultdict(int)
    for s in sessions:
        for k, v in s["mcp"].items(): mcp[k] += v
    return dict(sessions=sessions, stats=stats, cost=sum(s["cost"] for s in sessions),
                turns=sum(s["turns"] for s in sessions), mcp=mcp,
                bash=[c for s in sessions for c in s["bash"]])


def session_summary(s):
    """One session as plain JSON-serialisable data (used by --json)."""
    return {"id": os.path.splitext(os.path.basename(s["file"]))[0], "start": s["start"], "model": s["model"],
            "turns": s["turns"], "cost": round(s["cost"], 4), "cost_as_cheaper": round(s["as_cheaper"], 4),
            "tokens": dict(s["tokens"]), "spent": {k: round(v, 4) for k, v in s["spent"].items()},
            "peak_context": s["peak"], "cold_restarts": s["rebuilds"], "hook_runs": s["hook_runs"],
            "tips": session_tips(s)}

def project_summary(name, p, show):
    done = sorted((x for x in p["sessions"] if x["turns"]), key=lambda x: x["start"], reverse=True)
    return {"project": name, "cost": round(p["cost"], 4), "turns": p["turns"], "tokens": dict(p["stats"]),
            "sessions_total": len(done), "tips": advise(p), "mcp_used": dict(p["mcp"]),
            "sessions": [session_summary(x) for x in done[:show]]}

def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

def main():
    frag, show = arg("--project"), int(arg("--sessions", 5))
    try: since, until = date_range(sys.argv)
    except (ValueError, IndexError):
        sys.exit("tokenwatch: --since/--until need a date like 2026-10-01")
    rows = []
    for pdir in sorted(glob.glob(os.path.join(PROJECTS, "*"))):
        if not os.path.isdir(pdir): continue
        name = project_name(pdir)
        if frag and frag.lower() not in name.lower(): continue
        p = scan_project(pdir, since, until)
        if p["turns"] == 0: continue
        rows.append((p["cost"], name, p))
    rows.sort(key=lambda r: -r[0])
    if "--daily" in sys.argv:
        today = date.today()
        lo, hi = since or today - timedelta(days=13), until or today
        if lo > hi: sys.exit("tokenwatch: --since is after --until")
        mine = [scan_session(f) for d in glob.glob(os.path.join(PROJECTS, "*")) if os.path.isdir(d)
                and (not frag or frag.lower() in project_name(d).lower())
                for f in glob.glob(os.path.join(d, "*.jsonl"))]
        days = daily_totals(mine, lo, hi)
        if "--json" in sys.argv:
            print(json.dumps({"days": [{"date": d.isoformat(), "cost": round(c, 4)} for d, c in days],
                              "total_cost": round(sum(c for _, c in days), 4)}, indent=2))
        else:
            print("\n".join(trend_lines(days)))
            print(f"\n🤖 {len(days)} days: 🪙 ≈{money(sum(c for _, c in days))} at API list prices")
        return
    try: budget = parse_budget(sys.argv)
    except (ValueError, IndexError):
        sys.exit("tokenwatch: --budget needs a positive amount (e.g. --budget 20 --period week|day|month)")
    b = None
    if budget:
        lo, hi = period_range(budget[1])
        # a budget covers everything you spent, so ignore --project and the date filters here
        everything = [scan_session(f) for f in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))]
        b = budget_status(spend_between(everything, lo, hi), *budget)
    if "--json" in sys.argv:
        print(json.dumps({"total_cost": round(sum(r[0] for r in rows), 4),
                          "total_tokens": sum(sum(r[2]["stats"].values()) for r in rows), "budget": b,
                          "projects": [project_summary(n, p, show) for _, n, p in rows]}, indent=2))
        return
    grand = burnt = 0
    for cost, name, p in rows:
        s = p["stats"]
        grand += cost; burnt += sum(s.values())
        print(f"\n🤖 ━━ {name}")
        print(f"   🪙 ≈{money(cost)} · 🔥 {fmt(sum(s.values()))} tokens burnt · {len(p['sessions'])} session(s) · {p['turns']} turns")
        print(f"   out {fmt(s['output_tokens'])} · in {fmt(s['input_tokens'])} · "
              f"cache w {fmt(s['cache_creation_input_tokens'])} / r {fmt(s['cache_read_input_tokens'])}")
        for t in advise(p): print(f"   {t}")
        done = sorted((x for x in p["sessions"] if x["turns"]), key=lambda x: x["start"], reverse=True)
        for x in done[:show]:
            sp = x["spent"]
            print(f"\n   ▸ {when(x['start'])} · 🪙 ≈{money(x['cost'])} · 🔥 {fmt(sum(x['tokens'].values()))} tokens · "
                  f"{x['turns']} turns · {nice(x['model'])}")
            print(f"     where it went: re-reading history {money(sp['read'])} · saving history {money(sp['write'])} · "
                  f"Claude's writing {money(sp['out'])} · new input {money(sp['in'])}")
            for t in session_tips(x) or ["✓ nothing to fix"]: print(f"     💡 {t}" if t[0] != "✓" else f"     😺 {t[2:]}")
        if len(done) > show: print(f"\n   (+{len(done) - show} older session(s): --sessions {len(done)})")
    if b: print(f"\n{budget_line(b)}")
    print(f"\n🤖 ═══ all projects: 🪙 ≈{money(grand)} at API list prices · 🔥 {fmt(burnt)} tokens burnt")

if __name__ == "__main__":
    main()
