"""Per-day cost trend: zero-filled daily totals, sparkline and table."""
from datetime import timedelta
from twlib.fmt import money

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
