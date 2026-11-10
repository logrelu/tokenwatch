"""--theme weather: the dashboard data as a parody weather report, presented by Purr the meteorologist.

Same numbers as the classic dashboard (it renders dashboard.collect() output), only the framing changes.
Self-contained like the classic page: inline CSS and SVG icons, native title tooltips, no script, no images,
no external resources. Every string from the data goes through esc().
"""
import math
from datetime import date
from twlib.dashboard import esc, table, SPENT_PARTS
from twlib.fmt import fmt, money

# ---- the jokes, as pure functions (tested) ----

# condition key -> (label, one-liner). Ordered from calm to wild.
CONDITIONS = {
    "clear":  ("Clear skies", "Wallet unharmed"),
    "sunny":  ("Sunny", "Light spending, pleasant"),
    "partly": ("Partly cloudy", "Some spending moving in"),
    "rain":   ("Showers", "Steady downpour of tokens"),
    "storm":  ("Thunderstorms", "Spending well above pace"),
}

# cost type -> (precipitation, what it really is)
PRECIP = {"read": "Drizzle", "write": "Hail", "out": "Rain", "in": "Dew"}

# tip prefix -> advisory name. First match wins; anything else is a Special Weather Statement.
ADVISORIES = (
    ("long chat", "Flood Warning"),
    ("cold restarts", "Freeze Warning"),
    ("plugin hooks", "Wind Advisory"),
    ("model:", "Heat Advisory"),
    ("heavy session start", "Dense Fog Advisory"),
)

STORM_NAMES = ("Alberto", "Beryl", "Chris", "Debby", "Ernesto", "Francine", "Gordon", "Helene", "Isaac", "Joyce")

PRESSURE = {
    "ok":   ("Steady", "Fair weather: spending is on track."),
    "warn": ("Falling", "Storm watch: 80% of the budget is gone."),
    "over": ("Crashing", "Severe cost warning: the budget is blown."),
}


def _lc(label):
    """Lower-case a label for use mid-sentence, but keep proper nouns: "Claude's writing" stays capitalised."""
    return label if label.startswith("Claude") else label[:1].lower() + label[1:]


def reference(days, pace):
    """The 'normal' daily spend that weather is judged against: the budget pace, or else the average
    of the days that had any spend."""
    if pace: return pace
    spent = [d["cost"] for d in days if d["cost"] > 0]
    return sum(spent) / len(spent) if spent else 0.0


def condition(cost, ref):
    """Weather for one day: clear with no spend, then sunny / partly cloudy / showers / thunderstorms as
    the day's cost goes from under half of `ref` to over 1.5x it."""
    if cost <= 0: return "clear"
    if ref <= 0: return "sunny"
    r = cost / ref
    return "sunny" if r < 0.5 else "partly" if r < 1.0 else "rain" if r < 1.5 else "storm"


def advisory(tip):
    t = tip.lstrip("⚠◦ ").lower()
    for prefix, name in ADVISORIES:
        if t.startswith(prefix): return name
    return "Special Weather Statement"


def storm_category(cost, top):
    """1-5 like the hurricane scale, relative to the most expensive session shown."""
    return 1 if top <= 0 else max(1, min(5, 1 + int(4 * cost / top + 1e-9)))


def overall(data):
    """The headline condition for the whole period, from the budget if set, else from the busiest day."""
    b = data["budget"]
    if b: return {"ok": "sunny", "warn": "rain", "over": "storm"}[b["level"]] if data["totals"]["cost"] else "clear"
    days = data["daily"]
    ref = reference(days, data["budget_pace"])
    worst = max((condition(d["cost"], ref) for d in days), key=list(CONDITIONS).index, default="clear")
    return worst


def forecast_text(data):
    """Purr's opening lines, from the numbers."""
    t, b, days, spent = data["totals"], data["budget"], data["daily"], data["spent"]
    if t["cost"] <= 0:
        return ["Good evening, I'm Purr. Clear skies across all regions: not a token in sight."]
    lines = ["Good evening, I'm Purr, and here is your token forecast."]
    busiest = max(days, key=lambda d: d["cost"]) if days else None
    if busiest and busiest["cost"] > 0:
        lines.append("The stormiest day was %s, with %s coming down." % (_day(busiest["date"]), money(busiest["cost"])))
    total = sum(spent.values())
    if total > 0:
        k = max(spent, key=spent.get)
        label = _lc(dict(SPENT_PARTS)[k])
        lines.append("Expect a %.0f%% chance of %s (%s) through the evening." % (spent[k] / total * 100, PRECIP[k].lower(), label))
    if b:
        lines.append("Budget pressure is %s at %.0f%%. %s" % (PRESSURE[b["level"]][0].lower(), b["used"] * 100, PRESSURE[b["level"]][1]))
    else:
        lines.append("No budget front on the map tonight; add one with --budget.")
    return lines


def _day(iso):
    d = date.fromisoformat(iso)
    return "%s %d %s" % (d.strftime("%a"), d.day, d.strftime("%b"))


# ---- icons: inline SVG <symbol>s, no external files ----

ICONS = """<svg width="0" height="0" style="position:absolute" aria-hidden="true">
<symbol id="i-sun" viewBox="0 0 64 64"><g class="sun"><circle cx="32" cy="32" r="12"/>
<g stroke-width="4" stroke-linecap="round"><path d="M32 6v8M32 50v8M6 32h8M50 32h8M13.6 13.6l5.7 5.7M44.7 44.7l5.7 5.7M13.6 50.4l5.7-5.7M44.7 19.3l5.7-5.7"/></g></g></symbol>
<symbol id="i-cloud" viewBox="0 0 64 64"><path class="cloud" d="M18 48h28a10 10 0 0 0 1-20 14 14 0 0 0-27-3 11 11 0 0 0-2 23z"/></symbol>
<symbol id="i-clear" viewBox="0 0 64 64"><use href="#i-sun"/></symbol>
<symbol id="i-sunny" viewBox="0 0 64 64"><use href="#i-sun"/></symbol>
<symbol id="i-partly" viewBox="0 0 64 64"><g transform="translate(-8 -8) scale(.8)"><use href="#i-sun"/></g><g transform="translate(6 6) scale(.85)"><use href="#i-cloud"/></g></symbol>
<symbol id="i-rain" viewBox="0 0 64 64"><g transform="translate(0 -6)"><use href="#i-cloud"/></g>
<g class="drop" stroke-width="3.5" stroke-linecap="round"><path d="M22 50l-3 7M33 50l-3 7M44 50l-3 7"/></g></symbol>
<symbol id="i-storm" viewBox="0 0 64 64"><g transform="translate(0 -6)"><use href="#i-cloud" class="dark"/></g>
<path class="bolt" d="M34 40l-8 12h7l-4 10 12-15h-7l4-7z"/></symbol>
</svg>"""


def icon(key, size=48, label=None):
    title = "<title>%s</title>" % esc(label) if label else ""
    return '<svg class="ic ic-%s" width="%d" height="%d" viewBox="0 0 64 64" role="img"%s>%s<use href="#i-%s"/></svg>' % (
        key, size, size, ' aria-label="%s"' % esc(label) if label else ' aria-hidden="true"', title, key)


# ---- page sections ----

def forecast_cards(days, ref):
    cards = []
    for d in days:
        key = condition(d["cost"], ref)
        label, quip = CONDITIONS[key]
        tip = "%s: %s, %s. %s" % (_day(d["date"]), label, money(d["cost"]), quip)
        cards.append('<li class="day %s" title="%s" tabindex="0"><b>%s</b>%s<span class="hi">%s</span><span class="cond">%s</span></li>'
                     % (key, esc(tip), esc(_day(d["date"]).split(" ")[0]), icon(key, 44, label),
                        esc(money(d["cost"])), esc(label)))
    return '<ol class="days">%s</ol>' % "".join(cards)


def barometer(b):
    if not b:
        return '<p class="cap">No budget set, so no pressure reading. Try <code>--budget 25 --period week</code>.</p>'
    name, line = PRESSURE[b["level"]]
    pct = min(1.0, b["used"])
    # a half-dial: the needle swings from left (empty) to right (budget used up)
    ang = math.pi * (1 - pct)
    x, y = 100 + 70 * math.cos(ang), 90 - 70 * math.sin(ang)
    where = {"day": "today", "week": "the last 7 days", "month": "this month"}[b["period"]]
    dial = ('<svg class="dial" viewBox="0 0 200 110" role="img" aria-label="Budget used %.0f%%"><title>%s of %s budget used (%.0f%%)</title>'
            '<path class="arc" d="M30 90a70 70 0 0 1 140 0"/>'
            '<path class="arc fill %s" d="M30 90a70 70 0 0 1 %.1f %.1f" />'
            '<line class="needle" x1="100" y1="90" x2="%.1f" y2="%.1f"/><circle class="hub" cx="100" cy="90" r="6"/>'
            '<text x="30" y="106" class="tick">0%%</text><text x="170" y="106" class="tick end">100%%</text></svg>'
            % (b["used"] * 100, esc(money(b["spent"])), esc(money(b["budget"])), b["used"] * 100, b["level"],
               x - 30, y - 90, x, y))
    return ('<div class="baro">%s<div><div class="pressure %s">%s</div><p>%s</p><p class="cap">%s of %s spent %s (%.0f%%).</p></div></div>'
            % (dial, b["level"], esc(name), esc(line), esc(money(b["spent"])), esc(money(b["budget"])), esc(where), b["used"] * 100))


def radar(spent):
    total = sum(spent.values())
    if total <= 0: return '<p class="cap">No precipitation recorded.</p>'
    segs, legend = [], []
    for i, (k, label) in enumerate(SPENT_PARTS, 1):
        v = spent.get(k, 0.0); share = v / total
        legend.append('<li><i class="sw c%d"></i><b>%s</b> %s · %.0f%%</li>' % (i, esc(PRECIP[k]), esc(_lc(label)), share * 100))
        if v > 0:
            segs.append('<span class="seg c%d" style="flex:%.4f" title="%s: %s, %s (%.0f%%)">%s</span>'
                        % (i, share, esc(PRECIP[k]), esc(label), esc(money(v)), share * 100,
                           esc("%.0f%%" % (share * 100)) if share >= 0.12 else ""))
    return '<div class="segbar" role="img" aria-label="Cost split">%s</div><ul class="legend">%s</ul>' % ("".join(segs), "".join(legend))


def regions(projects):
    rows = []
    top = max((p["cost"] for p in projects), default=0)
    for p in projects:
        share = p["cost"] / top if top else 0
        key = "storm" if share >= 0.75 else "rain" if share >= 0.4 else "partly" if share >= 0.1 else "sunny"
        rows.append('<li title="%s: %s">%s<span class="rname">%s</span><span class="rbar"><i style="width:%.1f%%"></i></span><b>%s</b></li>'
                    % (esc(p["name"]), esc(money(p["cost"])), icon(key, 28, CONDITIONS[key][0]), esc(p["name"]),
                       max(share * 100, 1.5), esc(money(p["cost"]))))
    return '<ul class="regions">%s</ul>' % "".join(rows) if rows else '<p class="cap">No regions reporting.</p>'


def storms(sessions):
    if not sessions: return '<p class="cap">No storms tracked. Quiet season.</p>'
    top = max(s["cost"] for s in sessions)
    rows = []
    for i, s in enumerate(sessions):
        cat = storm_category(s["cost"], top)
        rows.append('<li><span class="cat c%d" title="Category %d">%d</span><div><b>Storm %s</b>'
                    '<span class="cap">%s · %s · %s</span></div><span class="sv">%s<small>winds %s turns</small></span></li>'
                    % (cat, cat, cat, esc(STORM_NAMES[i % len(STORM_NAMES)]), esc(s["date"]), esc(s["project"]),
                       esc(s["model"]), esc(money(s["cost"])), esc(s["turns"])))
    return '<ol class="storms">%s</ol>' % "".join(rows)


def advisories(tips):
    if not tips: return '<p class="cap">No advisories in effect. Enjoy the weather. 😺</p>'
    return '<ul class="adv">%s</ul>' % "".join(
        '<li><b>⚠ %s</b><span>%s</span><small>%s</small></li>' % (esc(advisory(t["text"])), esc(t["text"].lstrip("⚠◦ ")), esc(t["project"]))
        for t in tips)


STYLE = """
:root{color-scheme:light;--page:#eef3f8;--surface:#fff;--ink:#0b1320;--ink2:#46505e;--muted:#5f6977;--ring:rgba(11,19,32,.10);
--grid:#dfe5ec;--c1:#2a78d6;--c2:#eb6834;--c3:#1baf7a;--c4:#eda100;--on4:#0b0b0b;--good:#0c8a0c;--warn:#b26b00;--crit:#c42f2f;
--sun:#f5b400;--cloud:#c9d2dc;--cloud2:#6b7684;--drop:#2a78d6;--bolt:#f5b400}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0b1018;--surface:#151c26;
--ink:#eef2f7;--ink2:#b9c2ce;--muted:#98a2af;--ring:rgba(255,255,255,.10);--grid:#26303c;--c1:#3987e5;--c2:#d95926;
--c3:#199e70;--c4:#c98500;--on4:#fff;--good:#3fbf3f;--warn:#f0a43a;--crit:#ef6b6b;--cloud:#8793a1;--cloud2:#4a5563}}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:16px 16px 40px}
.sky{border-radius:16px;padding:20px;color:#fff;margin-bottom:16px;position:relative;overflow:hidden}
.sky.clear,.sky.sunny{background:linear-gradient(160deg,#1d5fb8,#3b8ee8 60%,#f0a43a)}
.sky.partly{background:linear-gradient(160deg,#2f5a8a,#5e86b0)}
.sky.rain{background:linear-gradient(160deg,#2d3b4f,#51637a)}
.sky.storm{background:linear-gradient(160deg,#1a1430,#3d2f5c 60%,#5b3f6e)}
.live{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.08em;background:#c42f2f;color:#fff;border-radius:4px;padding:2px 6px}
.sky h1{font-size:15px;margin:10px 0 0;font-weight:600;opacity:.95}
.now{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin-top:6px}
.now .temp{font-size:64px;font-weight:700;line-height:1}
.now .feels{font-size:14px;opacity:.95}
.now .ic{width:88px;height:88px}
.purr{display:flex;gap:12px;align-items:flex-start;margin-top:14px;background:rgba(0,0,0,.22);border-radius:12px;padding:12px}
.purr .face{font-size:34px;line-height:1}
.purr p{margin:0 0 4px;font-size:14px}
.stats{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:12px;font-size:13px;opacity:.95}
.sky .sun{fill:var(--sun);stroke:var(--sun)}.sky .cloud{fill:#eef2f7}.sky .dark .cloud,.sky .ic-storm .cloud{fill:#9aa6b4}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:16px;margin-bottom:16px}
.card h2{font-size:16px;margin:0 0 2px}
.cap{color:var(--ink2);font-size:13px;margin:0 0 10px}
.sun{fill:var(--sun);stroke:var(--sun)}.cloud{fill:var(--cloud)}.ic-storm .cloud{fill:var(--cloud2)}
.drop{stroke:var(--drop)}.bolt{fill:var(--bolt)}
.days{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(92px,1fr));gap:8px;padding:0;margin:0}
.day{display:flex;flex-direction:column;align-items:center;gap:2px;padding:10px 6px;border-radius:10px;border:1px solid var(--ring);outline:none;text-align:center}
.day:hover,.day:focus{border-color:var(--c1)}
.day b{font-size:13px}.day .hi{font-weight:700;font-variant-numeric:tabular-nums}.day .cond{font-size:11px;color:var(--ink2)}
.day.storm{background:color-mix(in srgb,var(--crit) 10%,transparent)}.day.rain{background:color-mix(in srgb,var(--c1) 8%,transparent)}
.baro{display:flex;gap:16px;align-items:center;flex-wrap:wrap}
.dial{width:200px;max-width:100%}
.arc{fill:none;stroke:var(--grid);stroke-width:14;stroke-linecap:round}
.arc.fill.ok{stroke:var(--good)}.arc.fill.warn{stroke:var(--warn)}.arc.fill.over{stroke:var(--crit)}
.needle{stroke:var(--ink);stroke-width:3;stroke-linecap:round}.hub{fill:var(--ink)}
.tick{fill:var(--muted);font-size:10px;text-anchor:middle}.tick.end{text-anchor:middle}
.pressure{font-size:22px;font-weight:700}.pressure.ok{color:var(--good)}.pressure.warn{color:var(--warn)}.pressure.over{color:var(--crit)}
.baro p{margin:2px 0}
.segbar{display:flex;gap:2px;height:28px}
.seg{display:flex;align-items:center;padding-left:8px;border-radius:4px;font-size:12px;font-weight:600;color:#fff;white-space:nowrap}
.seg.c4{color:var(--on4)}
.c1{background:var(--c1)}.c2{background:var(--c2)}.c3{background:var(--c3)}.c4{background:var(--c4)}
.legend{list-style:none;display:flex;flex-wrap:wrap;gap:4px 16px;padding:0;margin:8px 0 0;font-size:13px;color:var(--ink2)}
.legend b{color:var(--ink)}
.legend .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
.regions,.storms,.adv{list-style:none;padding:0;margin:0;display:grid;gap:8px}
.regions li{display:grid;grid-template-columns:28px minmax(90px,32%) 1fr auto;gap:10px;align-items:center;font-size:13px}
.rname{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ink2)}
.rbar{height:10px;background:var(--grid);border-radius:5px;overflow:hidden}.rbar i{display:block;height:100%;background:var(--c1);border-radius:5px}
.storms li{display:grid;grid-template-columns:36px 1fr auto;gap:10px;align-items:center;padding:8px;border:1px solid var(--ring);border-radius:10px}
.cat{width:32px;height:32px;border-radius:50%;display:grid;place-items:center;font-weight:700;color:#fff}
.cat.c1{background:#4f8fd6}.cat.c2{background:#3a9e6f}.cat.c3{background:#c98500}.cat.c4{background:#d95926}.cat.c5{background:#c42f2f}
.storms .cap{display:block;margin:0}.sv{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}.sv small{display:block;font-weight:400;color:var(--muted)}
.adv li{border-left:4px solid var(--warn);padding:6px 10px;background:color-mix(in srgb,var(--warn) 8%,transparent);border-radius:0 8px 8px 0}
.adv b{display:block;color:var(--warn)}.adv span{display:block;font-size:14px}.adv small{color:var(--muted)}
details{margin-top:12px}summary{cursor:pointer;color:var(--ink2);font-size:13px}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--grid);white-space:nowrap}
th{color:var(--ink2);font-weight:600}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px}.grid2 .card{margin-bottom:0}
.grid2{margin-bottom:16px}
code{font-size:12px}
footer{color:var(--muted);font-size:12px;margin-top:8px}
@media (max-width:520px){.now .temp{font-size:52px}.regions li{grid-template-columns:28px 1fr auto}.rbar{grid-column:2/-1;order:4}}
"""


def render(data):
    """The weather-report page as one HTML string (no external resources, no script)."""
    t, b, days = data["totals"], data["budget"], data["daily"]
    ref = reference(days, data["budget_pace"])
    now = overall(data)
    label, quip = CONDITIONS[now]
    span = "%s to %s" % (_day(days[0]["date"]), _day(days[-1]["date"])) if days else ""
    feels = ("Feels like %s of your %s budget" % (money(b["spent"]), money(b["budget"]))) if b else "No budget set"
    purr = "".join("<p>%s</p>" % esc(l) for l in forecast_text(data))
    face = {"clear": "😺", "sunny": "😺", "partly": "😼", "rain": "😿", "storm": "🙀"}[now]
    daily_rows = [(d["date"], CONDITIONS[condition(d["cost"], ref)][0], money(d["cost"])) for d in days]
    region_rows = [(p["name"], money(p["cost"])) for p in data["projects"]]
    precip_rows = [(PRECIP[k], label_, money(data["spent"].get(k, 0))) for k, label_ in SPENT_PARTS]
    storm_rows = [("Storm " + STORM_NAMES[i % len(STORM_NAMES)], s["date"], s["project"], s["model"], money(s["cost"]), s["turns"])
                  for i, s in enumerate(data["sessions"])]
    ref_note = ("Judged against your budget pace of %s a day." % money(data["budget_pace"])) if data["budget_pace"] else (
        "Judged against your average spending day (%s)." % money(ref) if ref else "No spending to judge.")
    body = (
        '<section class="sky %s"><span class="live">LIVE</span> <span class="live" style="background:rgba(0,0,0,.35)">%s</span>'
        '<h1>The Token Forecast · %s</h1>'
        '<div class="now">%s<div><div class="temp">%s</div><div class="feels">%s · %s</div><div class="feels">%s</div></div></div>'
        '<div class="purr"><span class="face" aria-hidden="true">%s</span><div>%s</div></div>'
        '<div class="stats"><span>🔥 %s tokens of humidity</span><span>☂ %s sessions</span><span>💨 %s turns</span></div></section>'
        % (now, esc(data["generated"]), esc(span), icon(now, 88, label), esc(money(t["cost"])), esc(label), esc(quip), esc(feels),
           face, purr, esc(fmt(t["tokens"])), esc(t["sessions"]), esc(t["turns"])))
    body += ('<section class="card"><h2>Your forecast</h2><p class="cap">%s Hover a day for details.</p>%s'
             '<details><summary>Show as table</summary>%s</details></section>'
             % (esc(ref_note), forecast_cards(days, ref), table(["Day", "Weather", "Spend"], daily_rows, num=(2,))))
    body += '<div class="grid2">'
    body += ('<section class="card"><h2>Barometer</h2><p class="cap">Budget pressure.</p>%s</section>' % barometer(b))
    body += ('<section class="card"><h2>Radar: precipitation by type</h2><p class="cap">Where the money came down.</p>%s'
             '<details><summary>Show as table</summary>%s</details></section>'
             % (radar(data["spent"]), table(["Precipitation", "What it is", "Spend"], precip_rows, num=(2,))))
    body += '</div>'
    body += ('<section class="card"><h2>Regional outlook</h2><p class="cap">Projects, wettest first.</p>%s'
             '<details><summary>Show as table</summary>%s</details></section>'
             % (regions(data["projects"]), table(["Region (project)", "Spend"], region_rows, num=(1,))))
    body += ('<section class="card"><h2>Storm tracker</h2><p class="cap">The most expensive sessions, by category (5 = the worst one shown).</p>%s'
             '<details><summary>Show as table</summary>%s</details></section>'
             % (storms(data["sessions"]), table(["Storm", "Date", "Region", "Model", "Spend", "Turns"], storm_rows, num=(4, 5))))
    body += ('<section class="card"><h2>Weather advisories</h2><p class="cap">What to do about it.</p>%s</section>' % advisories(data["tips"]))
    body += ('<footer>A parody, not a weather service. Costs are estimates at public API list prices. This file contains your '
             'project names: don\'t share it publicly. Generated locally by tokenwatch; it makes no network requests.</footer>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>tokenwatch forecast</title><style>%s</style></head><body>%s<main>%s</main></body></html>' % (STYLE, ICONS, body))
