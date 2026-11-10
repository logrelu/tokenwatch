"""Dates: session start day, --since/--until/--today/--week windows and budget periods."""
from datetime import datetime, date, timedelta

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
