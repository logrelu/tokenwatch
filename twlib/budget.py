"""Spending budget: parsing, spend in a period, status level and the printed line."""
import os
from twlib import prefs
from twlib.dates import PERIODS
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
