"""Static HTML dashboard (--export html): numbers first, drawing second.

Everything here is local: the page is one self-contained file (inline CSS, inline SVG, a tiny inline
script for tooltips) with no network access of any kind.
"""
import glob, html, json, os, calendar
from datetime import date, timedelta
from twlib import config
from twlib.budget import budget_status, spend_between
from twlib.dates import session_date, period_range
from twlib.fmt import fmt, money, nice
from twlib.scan import scan_project, project_name
from twlib.tips import session_tips, advise
from twlib.trend import daily_totals

TOP_PROJECTS = 8      # projects drawn on their own; the rest fold into "Other"
TOP_SESSIONS = 10
MAX_TIPS = 8
DEFAULT_DAYS = 14

# the four parts of a session's cost, in the fixed order (and colour slot) they are always drawn in
SPENT_PARTS = (("read", "Re-reading history"), ("write", "Saving history"),
               ("out", "Claude's writing"), ("in", "New input"))


def collect(frag=None, since=None, until=None, budget=None, today=None):
    """Scan transcripts under config.PROJECTS (read-only) and return the dashboard numbers as a
    plain dict. `budget` is (amount, period) or None. Raises ValueError if since is after until."""
    today = today or date.today()
    lo, hi = since or today - timedelta(days=DEFAULT_DAYS - 1), until or today
    if lo > hi: raise ValueError("since is after until")
    rows, shown, everything = [], [], []   # rows: (cost, name, project); shown: sessions behind the daily chart
    for pdir in sorted(glob.glob(os.path.join(config.PROJECTS, "*"))):
        if not os.path.isdir(pdir): continue
        name = project_name(pdir)
        if frag and frag.lower() not in name.lower():
            if budget: everything += scan_project(pdir)["sessions"]   # a budget ignores --project
            continue
        p = scan_project(pdir, since, until)
        full = scan_project(pdir)["sessions"] if (since or until) else p["sessions"]
        shown += full; everything += full
        if p["turns"]: rows.append((p["cost"], name, p))
    rows.sort(key=lambda r: -r[0])

    sessions = [(name, s) for _, name, p in rows for s in p["sessions"] if s["turns"]]
    spent = {k: sum(s["spent"][k] for _, s in sessions) for k, _ in SPENT_PARTS}
    top = sorted(sessions, key=lambda t: -t[1]["cost"])[:TOP_SESSIONS]
    projects = [{"name": n, "cost": round(c, 4)} for c, n, _ in rows[:TOP_PROJECTS]]
    if len(rows) > TOP_PROJECTS:
        projects.append({"name": "Other (%d more)" % (len(rows) - TOP_PROJECTS),
                         "cost": round(sum(r[0] for r in rows[TOP_PROJECTS:]), 4), "other": True})
    tips = []
    for c, name, p in rows:
        tips += [(name, t) for t in advise(p) if t.startswith("⚠")]
    for name, s in top:
        tips += [(name, t) for t in session_tips(s)]

    b, pace = None, None
    if budget:
        blo, bhi = period_range(budget[1], today)
        b = budget_status(spend_between(everything, blo, bhi), *budget)
        ndays = {"day": 1, "week": 7, "month": calendar.monthrange(today.year, today.month)[1]}[budget[1]]
        pace = round(budget[0] / ndays, 4)   # the budget spread evenly over its period
    mood = "🙀" if b and b["level"] == "over" else "😿" if b and b["level"] == "warn" else "😼" if tips else "😺"

    def day_of(s):
        d = session_date(s["start"])
        return d.isoformat() if d else ""
    return {
        "generated": today.isoformat(),
        "filter": {"project": frag or "", "since": since.isoformat() if since else "",
                   "until": until.isoformat() if until else ""},
        "mood": mood,
        "totals": {"cost": round(sum(r[0] for r in rows), 4), "tokens": sum(sum(r[2]["stats"].values()) for r in rows),
                   "sessions": len(sessions), "turns": sum(r[2]["turns"] for r in rows)},
        "daily": [{"date": d.isoformat(), "cost": round(c, 4)} for d, c in daily_totals(shown, lo, hi)],
        "budget": b, "budget_pace": pace,
        "projects": projects,
        "spent": {k: round(v, 4) for k, v in spent.items()},
        "sessions": [{"date": day_of(s), "project": n, "model": nice(s["model"]),
                      "cost": round(s["cost"], 4), "turns": s["turns"]} for n, s in top],
        "tips": [{"project": n, "text": t} for n, t in tips[:MAX_TIPS]],
    }
