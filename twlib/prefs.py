"""Saved settings: a budget and a dashboard theme, kept in config.PREFS so you set them once.

The file is tiny JSON, e.g. {"budget": "25/week", "theme": "weather"}. Values are checked when saved and
again when read, so a hand-edited or broken file is treated as empty instead of breaking a report.
"""
import json, os, tempfile
from twlib import config
from twlib.dates import PERIODS

THEMES = ("classic", "weather")      # same as dashboard.THEMES; kept here so prefs imports nothing heavy


def budget_text(amount, period):
    """(25.0, "week") -> "25/week"."""
    return "%g/%s" % (amount, period)


def parse_budget_text(text):
    """"25/week" or "25" -> (25.0, "week"). Raises ValueError on anything else."""
    raw, _, period = str(text).partition("/")
    amount, period = float(raw), period or "week"
    if not amount > 0 or amount == float("inf") or period not in PERIODS: raise ValueError("bad budget")
    return amount, period


def valid(key, value):
    if key == "budget":
        try: parse_budget_text(value); return True
        except ValueError: return False
    if key == "theme": return value in THEMES
    return False


def load():
    """The saved settings that are still valid, or {} when there is no (readable) file."""
    try:
        with open(config.PREFS, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict): return {}
    return {k: v for k, v in data.items() if valid(k, v)}


def save(changes):
    """Merge `changes` into the saved settings; a value of None removes that key. Returns the new settings."""
    for k, v in changes.items():
        if v is not None and not valid(k, v): raise ValueError(f"bad {k}: {v!r}")
    data = load()
    for k, v in changes.items():
        if v is None: data.pop(k, None)
        else: data[k] = v
    folder = os.path.dirname(config.PREFS)
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".config-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp, config.PREFS)          # all or nothing: never a half-written file
    except BaseException:
        if os.path.exists(tmp): os.unlink(tmp)
        raise
    return data


def describe(data):
    """One line for humans: what is saved."""
    if not data: return "nothing saved"
    parts = []
    if "budget" in data:
        amount, period = parse_budget_text(data["budget"])
        parts.append("budget $%g per %s" % (amount, period))
    if "theme" in data: parts.append("theme " + data["theme"])
    return ", ".join(parts)
