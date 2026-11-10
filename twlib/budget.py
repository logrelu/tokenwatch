"""Spending budget: parsing, spend in a period, status level and the printed line."""
import glob, json, os, time
from datetime import datetime, timedelta
from twlib import config, prefs
from twlib.dates import PERIODS, period_range
from twlib.fmt import money

def parse_budget(argv, env=None, saved=None):
    """(amount, period) from `--budget 20 [--period week]` / `--budget 20/week`, else TOKENWATCH_BUDGET=20/week,
    else the saved budget (prefs), else None. Raises ValueError on a bad flag or variable."""
    env = os.environ if env is None else env
    raw, period = None, "week"
    if "--budget" in argv:
        raw = argv[argv.index("--budget") + 1]
        if "/" in raw: return prefs.parse_budget_text(raw)
        if "--period" in argv: period = argv[argv.index("--period") + 1]
    elif env.get("TOKENWATCH_BUDGET"):
        raw, _, p = env["TOKENWATCH_BUDGET"].partition("/")
        period = p or period
    else:
        text = (prefs.load() if saved is None else saved).get("budget")
        return prefs.parse_budget_text(text) if text else None
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


LIVE_MAX_AGE = 300      # seconds the statusline reuses a computed budget total


def _changed_since(day):
    """Transcripts modified since the day before `day` (older files can't hold replies in the period)."""
    cutoff = (datetime.combine(day, datetime.min.time()) - timedelta(days=1)).timestamp()
    out = []
    for f in glob.glob(os.path.join(config.PROJECTS, "*", "*.jsonl")):
        try:
            if os.path.getmtime(f) >= cutoff: out.append(f)
        except OSError: pass
    return out


def live_budget(now=None, today=None, max_age=LIVE_MAX_AGE):
    """budget_status() for the saved/env budget, for the statusline: cached in config.OUT_DIR and recomputed
    at most every `max_age` seconds. None when no budget is set. Never raises."""
    from twlib.scan import scan_session          # here, so importing budget stays light for the CLI
    try:
        b = parse_budget([])
        if not b: return None
        now = time.time() if now is None else now
        lo, hi = period_range(b[1], today)
        key = "%s|%s|%s" % (prefs.budget_text(*b), lo, hi)
        cache = os.path.join(config.private_dir(), "budget.json")
        try:
            with open(cache, encoding="utf-8") as fh: c = json.load(fh)
            if c.get("key") == key and 0 <= now - c.get("t", 0) < max_age:
                return budget_status(c["spent"], *b)
        except (OSError, ValueError, KeyError, TypeError): pass
        spent = spend_between([scan_session(f) for f in _changed_since(lo)], lo, hi)
        tmp = cache + ".%d" % os.getpid()
        with open(tmp, "w", encoding="utf-8") as fh: json.dump({"key": key, "t": now, "spent": spent}, fh)
        os.replace(tmp, cache)
        return budget_status(spent, *b)
    except Exception:
        return None


def budget_segment(b, color=True, utf=True):
    """Short statusline text: "💰 64% of $25/week"; yellow from 80%, red when over (with a word, not colour alone)."""
    if not b: return ""
    text = "%s %s of %s/%s" % ("💰" if utf else "budget", "{:.0%}".format(b["used"]), "$%g" % b["budget"], b["period"])
    text += {"ok": "", "warn": " nearly there", "over": " OVER"}[b["level"]]
    code = {"ok": "", "warn": "33", "over": "31"}[b["level"]]
    return "\033[%sm%s\033[0m" % (code, text) if color and code else text
