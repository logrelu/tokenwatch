"""Number, money, model-name and date formatting helpers."""
from datetime import datetime

def fmt(n):
    for unit in ("", "K", "M", "B"):
        if abs(n) < 1000: return f"{n:,.0f}{unit}"
        n /= 1000
    return f"{n:.1f}T"

def money(x):
    return f"${x:,.2f}" if x < 100 else f"${x:,.0f}"

def nice(model):
    """claude-fable-5-1 -> Fable 5.1"""
    parts = (model or "").split("-")[1:]
    return (parts[0].title() + " " + ".".join(p for p in parts[1:] if len(p) < 3)).strip() if parts else "?"

def when(ts):
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
        return f"{t.day} {t:%b %H:%M}"
    except Exception:
        return "?"
