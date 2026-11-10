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
    every = max(1, -(-n // 6))   # about six x labels, however many days
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

STYLE = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#6b6a65;
--grid:#e1e0d9;--base:#c3c2b7;--ring:rgba(11,11,11,.10);--c1:#2a78d6;--c2:#eb6834;--c3:#1baf7a;--c4:#eda100;
--on1:#fff;--on2:#fff;--on3:#fff;--on4:#0b0b0b;--good:#0ca30c;--warn:#fab219;--crit:#d03b3b}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;
--ink:#f0efec;--ink2:#c3c2b7;--muted:#a09e96;--grid:#2c2c2a;--base:#383835;--ring:rgba(255,255,255,.10);
--c1:#3987e5;--c2:#d95926;--c3:#199e70;--c4:#c98500;--on4:#fff}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:960px;margin:0 auto;padding:20px 16px 40px}
header{display:flex;gap:12px;align-items:center;margin-bottom:16px}
header .mood{font-size:40px;line-height:1}
h1{font-size:22px;margin:0}
.sub{color:var(--ink2);font-size:13px;margin:2px 0 0}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px;margin-bottom:16px}
.card h2{font-size:15px;margin:0 0 2px}
.card .cap{color:var(--ink2);font-size:13px;margin:0 0 12px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:16px}
.kpi{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:14px 16px}
.kpi .l{color:var(--ink2);font-size:13px}
.kpi .v{font-size:28px;font-weight:600;margin-top:2px}
.kpi.hero .v{font-size:48px;line-height:1.1}
.kpi .c{color:var(--muted);font-size:12px;margin-top:2px}
.meter{height:8px;border-radius:4px;background:color-mix(in srgb,var(--c1) 18%,var(--surface));overflow:hidden;margin:8px 0 6px}
.meter i{display:block;height:100%;border-radius:4px;background:var(--c1)}
.meter.warn i{background:var(--warn)}.meter.over i{background:var(--crit)}
.chart{display:block;width:100%;height:auto}
.chart .grid{stroke:var(--grid);stroke-width:1}.chart .base{stroke:var(--base);stroke-width:1}
.chart .ax{fill:var(--muted);font-size:9px}
.chart .peak{fill:var(--ink);font-size:9.5px;font-weight:600}
.chart .bar{fill:var(--c1)}.chart .hit{fill:transparent}
.chart .col:hover .bar,.chart .col:focus .bar{fill:var(--ink)}.chart .col{outline:none}
.chart .pace{stroke:var(--ink2);stroke-width:2;stroke-dasharray:6 4}
.legend{list-style:none;display:flex;flex-wrap:wrap;gap:4px 16px;padding:0;margin:8px 0 0;font-size:13px;color:var(--ink2)}
.legend .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:baseline}
.legend .pl{display:inline-block;width:18px;border-top:2px dashed var(--ink2);margin-right:6px;vertical-align:middle}
.c1{background:var(--c1)}.c2{background:var(--c2)}.c3{background:var(--c3)}.c4{background:var(--c4)}
.pbars{display:grid;gap:8px}
.prow{display:grid;grid-template-columns:minmax(90px,32%) 1fr auto;gap:10px;align-items:center;font-size:13px;border-radius:6px;outline:none}
.prow:hover,.prow:focus{background:color-mix(in srgb,var(--ink) 6%,transparent)}
.pname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink2)}
.ptrack{display:block;height:12px}
.pbar{display:block;height:12px;min-width:2px;background:var(--c1);border-radius:0 4px 4px 0}
.prow.other .pbar{background:var(--base)}
.pval{font-weight:600;font-variant-numeric:tabular-nums}
.segbar{display:flex;gap:2px;height:28px}
.seg{display:flex;align-items:center;padding-left:8px;border-radius:4px;font-size:12px;font-weight:600;min-width:0;
overflow:visible;white-space:nowrap;outline:none}
.seg.c1{color:var(--on1)}.seg.c2{color:var(--on2)}.seg.c3{color:var(--on3)}.seg.c4{color:var(--on4)}
.seg:hover,.seg:focus{filter:brightness(1.12)}
.seg.empty{background:var(--grid);color:var(--ink2);flex:1}
details{margin-top:12px}summary{cursor:pointer;color:var(--ink2);font-size:13px}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);white-space:nowrap}
th{color:var(--ink2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
td.wrap{white-space:normal}
.tips{list-style:none;margin:0;padding:0;display:grid;gap:10px}
.tips li small{display:block;color:var(--muted)}
footer{color:var(--muted);font-size:12px;margin-top:8px}
#tip{position:fixed;z-index:9;pointer-events:none;background:var(--ink);color:var(--surface);padding:4px 8px;
border-radius:6px;font-size:12px;font-weight:600;display:none;max-width:260px}
@media (max-width:520px){.chart .ax,.chart .peak{font-size:20px}.kpi.hero .v{font-size:40px}.prow{grid-template-columns:1fr auto}
.ptrack{grid-column:1/-1;order:3}}
"""

# hover/focus tooltips only; text goes in with textContent
SCRIPT = """
(function(){var t=document.getElementById('tip');
function show(e,el){t.textContent=el.getAttribute('data-tip');t.style.display='block';
var r=el.getBoundingClientRect(),x=e&&e.clientX!==undefined?e.clientX:r.left+r.width/2,y=e&&e.clientY!==undefined?e.clientY:r.top;
t.style.left=Math.max(4,Math.min(innerWidth-t.offsetWidth-4,x+12))+'px';t.style.top=Math.max(4,y-t.offsetHeight-10)+'px'}
function hide(){t.style.display='none'}
document.querySelectorAll('[data-tip]').forEach(function(el){
el.addEventListener('pointermove',function(e){show(e,el)});el.addEventListener('pointerleave',hide);
el.addEventListener('focus',function(){show(null,el)});el.addEventListener('blur',hide)})})();
"""

def _json_for_script(data):
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/").replace("<!--", "<\\!--")

def _filter_text(f):
    bits = [f["project"] and "project contains \"%s\"" % f["project"],
            (f["since"] or f["until"]) and "%s to %s" % (f["since"] or "start", f["until"] or "today")]
    return ", ".join(b for b in bits if b) or "all projects, all time"

def render_html(data):
    """The whole dashboard as one HTML string (no external resources)."""
    t, b = data["totals"], data["budget"]
    days, spent = data["daily"], data["spent"]
    span = "%s to %s" % (_day(days[0]["date"]), _day(days[-1]["date"])) if days else ""
    kpi = lambda label, val, cap="", hero="": ('<div class="kpi%s"><div class="l">%s</div><div class="v">%s</div>%s</div>'
                                              % (hero, esc(label), esc(val), '<div class="c">%s</div>' % esc(cap) if cap else ""))
    parts = ['<!doctype html><html lang="en"><head><meta charset="utf-8">'
             '<meta name="viewport" content="width=device-width,initial-scale=1">'
             '<title>tokenwatch dashboard</title><style>', STYLE, '</style></head><body><main>']
    parts.append('<header><div class="mood" aria-hidden="true">%s</div><div><h1>tokenwatch</h1>'
                 '<p class="sub">Generated %s &middot; %s</p></div></header>'
                 % (esc(data["mood"]), esc(data["generated"]), esc(_filter_text(data["filter"]))))
    parts.append('<div class="kpis">%s%s%s%s</div>' % (
        kpi("Total cost", money(t["cost"]), "estimate at API list prices, not your bill", " hero"),
        kpi("Tokens burnt", fmt(t["tokens"]), "everything sent and received"),
        kpi("Sessions", fmt(t["sessions"]), "chats with Claude Code"),
        kpi("Turns", fmt(t["turns"]), "replies from Claude")))
    if b:
        where = {"day": "today", "week": "the last 7 days", "month": "this month"}[b["period"]]
        mood = {"over": "🙀 over budget", "warn": "😿 nearly there", "ok": "😺 on track"}[b["level"]]
        parts.append('<div class="card"><h2>Budget</h2><div class="meter %s" role="img" aria-label="%s used"><i style="width:%.1f%%"></i></div>'
                     '<p class="cap">%s: %s of %s (%.0f%%) &middot; %s</p></div>'
                     % (esc(b["level"]), esc("%.0f%%" % (b["used"] * 100)), min(100.0, b["used"] * 100), esc(where),
                        esc(money(b["spent"])), esc(money(b["budget"])), b["used"] * 100, esc(mood)))
    # daily cost
    legend = '<ul class="legend"><li><i class="sw c1"></i>Cost per day</li>'
    if data["budget_pace"]:
        legend += '<li><i class="pl"></i>Budget pace (%s a day)</li>' % esc(money(data["budget_pace"]))
    legend += "</ul>"
    parts.append('<section class="card"><h2>Cost per day</h2><p class="cap">%s</p>%s%s<details><summary>Show as table</summary>%s</details></section>'
                 % (esc(span), daily_chart(days, data["budget_pace"]), legend,
                    table(["Day", "Cost"], [(_day(d["date"]), money(d["cost"])) for d in days], num=(1,))))
    # projects
    parts.append('<section class="card"><h2>Cost by project</h2><p class="cap">Biggest first; small ones are folded into Other.</p>'
                 '%s<details><summary>Show as table</summary>%s</details></section>'
                 % (project_bars(data["projects"]) if data["projects"] else '<p class="cap">No usage found.</p>',
                    table(["Project", "Cost"], [(p["name"], money(p["cost"])) for p in data["projects"]], num=(1,))))
    # where the money went
    total = sum(spent.values())
    parts.append('<section class="card"><h2>Where the money went</h2><p class="cap">The same total, split by what Claude was doing.</p>'
                 '%s<details><summary>Show as table</summary>%s</details></section>'
                 % (spent_bar(spent), table(["Part", "Cost", "Share"],
                    [(lbl, money(spent.get(k, 0)), "%.0f%%" % (100.0 * spent.get(k, 0) / total if total else 0))
                     for k, lbl in SPENT_PARTS], num=(1, 2))))
    # sessions and tips
    parts.append('<section class="card"><h2>Top sessions</h2><p class="cap">The most expensive chats in this view.</p>%s</section>'
                 % (table(["Date", "Project", "Model", "Cost", "Turns"],
                          [(s["date"] or "?", s["project"], s["model"], money(s["cost"]), s["turns"]) for s in data["sessions"]],
                          num=(3, 4)) if data["sessions"] else '<p class="cap">No sessions found.</p>'))
    tips = "".join('<li>💡 %s<small>%s</small></li>' % (esc(x["text"].lstrip("⚠ ").strip()), esc(x["project"])) for x in data["tips"])
    parts.append('<section class="card"><h2>Tips</h2><ul class="tips">%s</ul></section>'
                 % (tips or "<li>😺 Nothing to fix.</li>"))
    parts.append('<footer>Costs are estimates at public API list prices. This file contains your project names: '
                 'don\'t share it publicly. Generated locally by tokenwatch; it makes no network requests.</footer></main>')
    parts.append('<div id="tip" role="status"></div><script type="application/json" id="tw-data">%s</script><script>%s</script></body></html>'
                 % (_json_for_script(data), SCRIPT))
    return "".join(parts)

def write_dashboard(path, data):
    """Write the dashboard to `path` and return the path."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_html(data))
    return path

def table(headers, rows, num=()):
    """A plain data table; every cell is escaped. `num` lists right-aligned column indexes."""
    head = "".join('<th%s>%s</th>' % (' class="n"' if i in num else "", esc(h)) for i, h in enumerate(headers))
    body = "".join("<tr>%s</tr>" % "".join('<td%s>%s</td>' % (' class="n"' if i in num else "", esc(c))
                                           for i, c in enumerate(r)) for r in rows)
    return '<div class="tw"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (head, body)
