"""Static HTML dashboard (--export html): numbers first, drawing second.

Everything here is local: the page is one self-contained file (inline CSS, inline SVG, a tiny inline
script for tooltips) with no network access of any kind.
"""
import calendar, glob, html, json, math, os
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


# ---- charts: each returns an HTML/SVG fragment; every string from data goes through esc() ----

def esc(s):
    return html.escape(str(s), quote=True)

def _day(iso):
    d = date.fromisoformat(iso)
    return "%d %s" % (d.day, d.strftime("%b"))

def _nice_ceiling(top):
    """(ymax, step) with 3-5 clean gridlines for a chart whose tallest value is `top`."""
    if top <= 0: return 1.0, 0.25
    raw = top / 4.0
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if m * mag >= raw: step = m * mag; break
    ymax = step
    while ymax < top: ymax += step
    return ymax, step

def _tick(v):
    return "$%d" % v if abs(v - round(v)) < 1e-9 else "$%.2f" % v

def _bar_path(x, y, w, h, r=4):
    """A column with a rounded top and a square foot."""
    r = min(r, w / 2.0, h)
    return ("M%.1f %.1f V%.1f Q%.1f %.1f %.1f %.1f H%.1f Q%.1f %.1f %.1f %.1f V%.1f Z"
            % (x, y + h, y + r, x, y, x + r, y, x + w - r, x + w, y, x + w, y + r, y + h))

def daily_chart(days, pace=None):
    """Column chart of cost per day (inline SVG); `pace` draws a budget reference line."""
    W, H, L, R, T, B = 600, 240, 46, 10, 14, 30
    pw, ph = W - L - R, H - T - B
    top = max([d["cost"] for d in days] + [pace or 0])
    ymax, step = _nice_ceiling(top)
    y_of = lambda v: T + ph * (1 - v / ymax)
    n = max(len(days), 1)
    slot = pw / n
    bw = max(1.5, min(24.0, slot - 2.0))   # thin bars; the rest of the slot is air
    out = ['<svg class="chart daily" viewBox="0 0 %d %d" role="img" aria-label="Cost per day">' % (W, H)]
    v = 0.0
    while v <= ymax + 1e-9:
        out.append('<line class="grid" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (L, W - R, y_of(v), y_of(v)))
        out.append('<text class="ax" x="%d" y="%.1f" text-anchor="end">%s</text>' % (L - 6, y_of(v) + 4, _tick(v)))
        v += step
    out.append('<line class="base" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (L, W - R, y_of(0), y_of(0)))
    every = max(1, -(-n // 7))   # about seven x labels, however many days
    best = max(range(len(days)), key=lambda i: days[i]["cost"]) if days and top > 0 else None
    for i, d in enumerate(days):
        cx = L + slot * (i + 0.5)
        h = ph * d["cost"] / ymax
        tip = "%s: %s" % (_day(d["date"]), money(d["cost"]))
        out.append('<g class="col" tabindex="0" data-tip="%s">' % esc(tip))
        out.append('<rect class="hit" x="%.1f" y="%d" width="%.1f" height="%d"/>' % (cx - slot / 2, T, slot, ph))
        if h >= 0.5:
            out.append('<path class="bar" d="%s"/>' % _bar_path(cx - bw / 2, y_of(0) - h, bw, h))
        out.append('</g>')
        if i % every == 0 or i == len(days) - 1 and (n - 1) % every == 0:
            out.append('<text class="ax x" x="%.1f" y="%d" text-anchor="middle">%s</text>' % (cx, H - 10, esc(_day(d["date"]))))
        if i == best:
            out.append('<text class="peak" x="%.1f" y="%.1f" text-anchor="middle">%s</text>'
                       % (min(max(cx, L + 18), W - R - 18), y_of(0) - h - 5, esc(money(d["cost"]))))
    if pace:
        out.append('<line class="pace" x1="%d" x2="%d" y1="%.1f" y2="%.1f"/>' % (L, W - R, y_of(pace), y_of(pace)))
    out.append('</svg>')
    return "".join(out)

def project_bars(projects):
    """Horizontal bars, biggest first: name, bar, value at the tip."""
    top = max([p["cost"] for p in projects] + [0]) or 1
    rows = []
    for p in projects:
        w = 100.0 * p["cost"] / top
        rows.append('<div class="prow%s" tabindex="0" data-tip="%s"><span class="pname">%s</span>'
                    '<span class="ptrack"><span class="pbar" style="width:%.1f%%"></span></span>'
                    '<span class="pval">%s</span></div>'
                    % (" other" if p.get("other") else "", esc("%s: %s" % (p["name"], money(p["cost"]))),
                       esc(p["name"]), w, esc(money(p["cost"]))))
    return '<div class="pbars">%s</div>' % "".join(rows)

def spent_bar(spent):
    """One segmented bar: where the money went, in fixed colour order, plus its legend."""
    total = sum(spent.values())
    segs, legend = [], []
    for i, (k, label) in enumerate(SPENT_PARTS, 1):
        v = spent.get(k, 0.0)
        share = v / total if total else 0
        tip = "%s: %s (%.0f%%)" % (label, money(v), share * 100)
        legend.append('<li><i class="sw c%d"></i>%s</li>' % (i, esc(label)))
        if v <= 0: continue
        text = "%.0f%%" % (share * 100) if share >= 0.12 else ""   # too narrow to label: tooltip and table carry it
        segs.append('<span class="seg c%d" style="flex:%.4f" tabindex="0" data-tip="%s">%s</span>'
                    % (i, share, esc(tip), esc(text)))
    if not segs: segs = ['<span class="seg empty">no spend yet</span>']
    return '<div class="segbar" role="img" aria-label="Cost split">%s</div><ul class="legend">%s</ul>' % ("".join(segs), "".join(legend))

def table(headers, rows, num=()):
    """A plain data table; every cell is escaped. `num` lists right-aligned column indexes."""
    head = "".join('<th%s>%s</th>' % (' class="n"' if i in num else "", esc(h)) for i, h in enumerate(headers))
    body = "".join("<tr>%s</tr>" % "".join('<td%s>%s</td>' % (' class="n"' if i in num else "", esc(c))
                                           for i, c in enumerate(r)) for r in rows)
    return '<div class="tw"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, body)
