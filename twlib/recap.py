"""The weekly recap: one line about last week (Monday to Sunday), shown by the greeting once per week."""
import glob, json, os, tempfile
from collections import defaultdict
from datetime import date, timedelta
from twlib import config, prefs
from twlib.fmt import money

today_fn = date.today        # replaced by examples/demo.py to render a fixed week


def weeks(today):
    """((last Monday, last Sunday), (the Monday before, the Sunday before)) relative to `today`."""
    monday = today - timedelta(days=today.weekday())
    last = (monday - timedelta(days=7), monday - timedelta(days=1))
    return last, (last[0] - timedelta(days=7), last[0] - timedelta(days=1))


def summarize(sessions, today):
    """sessions: [(project name, scanned session)]. Last week's cost, session count and priciest project,
    plus the week before's cost."""
    (lo, hi), (plo, phi) = weeks(today)
    cost = prev = 0.0
    count, by_project = 0, defaultdict(float)
    for name, s in sessions:
        this = sum(c for d, c in s["daily"].items() if lo <= d <= hi)
        prev += sum(c for d, c in s["daily"].items() if plo <= d <= phi)
        if this > 0:
            cost += this; count += 1; by_project[name] += this
    top = max(by_project.items(), key=lambda kv: kv[1]) if by_project else None
    return {"from": lo, "to": hi, "cost": cost, "sessions": count, "top": top, "prev": prev}


def _day(d):
    return "%d %s" % (d.day, d.strftime("%b"))


def recap_line(r):
    """The recap as one line, or None when last week cost nothing."""
    if r["cost"] < 0.005: return None
    parts = ["≈%s over %d session%s" % (money(r["cost"]), r["sessions"], "" if r["sessions"] == 1 else "s")]
    if r["top"] and r["sessions"] > 1:
        parts.append("priciest: %s (%s)" % (r["top"][0], money(r["top"][1])))
    if r["prev"] >= 0.005:
        change = (r["cost"] - r["prev"]) / r["prev"]
        parts.append("%s %.0f%% vs the week before" % ("↑" if change > 0 else "↓", abs(change) * 100)
                     if abs(change) >= 0.005 else "same as the week before")
    return "📅 tokenwatch: last week (%s – %s): %s" % (_day(r["from"]), _day(r["to"]), " · ".join(parts))


def scan_recent(today):
    """(project name, session) for transcripts touched since the day before the two weeks began."""
    from twlib.budget import _changed_since
    from twlib.scan import scan_session, project_name
    start = weeks(today)[1][0]
    return [(project_name(os.path.dirname(f)), scan_session(f)) for f in _changed_since(start)]


def build(today=None):
    today = today or today_fn()
    return recap_line(summarize(scan_recent(today), today))


def _monday(today):
    return (today - timedelta(days=today.weekday())).isoformat()


def due(today=None):
    """True when the recap hasn't been shown this week and isn't turned off."""
    if prefs.load().get("recap") == "off": return False
    try:
        with open(config.STATE, encoding="utf-8") as fh:
            return json.load(fh).get("shown_week") != _monday(today or today_fn())
    except (OSError, ValueError, AttributeError):
        return True


def mark_shown(today=None):
    folder = os.path.dirname(config.STATE)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".recap-")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"shown_week": _monday(today or today_fn())}, fh)
    os.replace(tmp, config.STATE)


def greeting_line(today=None):
    """For the SessionStart hook: the recap once per week (marked shown only when there was one)."""
    today = today or today_fn()
    if not due(today): return None
    line = build(today)
    if line: mark_shown(today)
    return line
