"""The tokenwatch command line: argument parsing and report printing."""
import glob, json, os, pathlib, sys, webbrowser
from datetime import date, timedelta
from twlib import args, config, dashboard, prefs, recap
from twlib.budget import parse_budget, spend_between, budget_status, budget_line
from twlib.prefs import budget_text
from twlib.dates import date_range, period_range
from twlib.fmt import fmt, money, nice, when
from twlib.report import project_summary
from twlib.scan import scan_session, scan_project, project_name
from twlib.tips import session_tips, advise
from twlib.trend import daily_totals, trend_lines

def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

# Replaced in tests so no real browser starts. Returns False when no browser could be opened.
open_browser = webbrowser.open


def agents_note(s):
    """' · incl. 2 agents ≈$1.20' when subagents added to a session's cost, else ''."""
    n = s.get("agents", 0)
    return f" · incl. {n} agent{'s' if n != 1 else ''} ≈{money(s['agent_cost'])}" if n else ""


def private_out_dir():
    """config.private_dir(), or exit with a message (symlink, someone else's folder, can't create)."""
    try: return config.private_dir()
    except PermissionError:
        sys.exit(f"tokenwatch: {config.OUT_DIR} is not a folder you own; pass --export html PATH instead")
    except OSError as e:
        sys.exit(f"tokenwatch: cannot create {config.OUT_DIR}: {e.strerror}; pass --export html PATH instead")


def export(frag, since, until):
    """--export html [PATH] and/or --open: write the static dashboard, say where it went, maybe open it."""
    opening, path = "--open" in sys.argv, None
    if "--export" in sys.argv:
        i = sys.argv.index("--export")
        rest = sys.argv[i + 1:i + 3]
        if not rest or rest[0] != "html": sys.exit("tokenwatch: --export html [PATH]")
        path = rest[1] if len(rest) > 1 and not rest[1].startswith("--") else None
    if path is None and opening:
        path = os.path.join(private_out_dir(), "dashboard.html")
    elif path is None:
        path = os.path.join(os.getcwd(), "tokenwatch-dashboard.html")
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if os.path.commonpath([here, os.path.abspath(path)]) == here:
            sys.exit("tokenwatch: not writing the dashboard inside the tokenwatch checkout; pass a PATH elsewhere")
    try: budget = parse_budget(sys.argv)
    except (ValueError, IndexError):
        sys.exit("tokenwatch: --budget needs a positive amount (e.g. --budget 20 --period week|day|month)")
    theme = arg("--theme") or prefs.load().get("theme", "classic")
    if theme not in dashboard.THEMES:
        sys.exit("tokenwatch: --theme must be one of: " + ", ".join(dashboard.THEMES))
    try: data = dashboard.collect(frag, since, until, budget)
    except ValueError: sys.exit("tokenwatch: --since is after --until")
    try: dashboard.write_dashboard(path, data, theme)
    except OSError as e: sys.exit("tokenwatch: cannot write %s: %s" % (path, e.strerror))
    print(f"🤖 dashboard written to {path}\n   it contains your project names; don't share it publicly")
    if opening:
        try: opened = open_browser(pathlib.Path(path).resolve().as_uri())
        except Exception: opened = False
        print("   opened in your browser" if opened else "   couldn't start a browser here; open the file above yourself")

SAVABLE = {"--save", "--budget", "--period", "--theme", "--recap", "--no-recap"}


def save_settings():
    """--save: remember --budget/--period and --theme (None forgets), or show what is saved."""
    extra = [a for a in sys.argv[1:] if a.startswith("--") and a not in SAVABLE]
    if extra: sys.exit("tokenwatch: --save only remembers --budget, --theme and --recap/--no-recap (drop %s)" % " ".join(extra))
    if "--recap" in sys.argv and "--no-recap" in sys.argv: sys.exit("tokenwatch: pick one of --recap and --no-recap")
    changes = {}
    if "--budget" in sys.argv:
        if arg("--budget").lower() in ("off", "none"): changes["budget"] = None
        else:
            try: changes["budget"] = budget_text(*parse_budget(sys.argv, env={}, saved={}))
            except (ValueError, IndexError):
                sys.exit("tokenwatch: --budget needs a positive amount and a period of day, week or month "
                         "(e.g. --budget 25/week, or --budget off)")
    if "--theme" in sys.argv:
        theme = arg("--theme")
        if theme not in dashboard.THEMES:
            sys.exit("tokenwatch: --theme must be one of: " + ", ".join(dashboard.THEMES))
        changes["theme"] = None if theme == "classic" else theme
    if "--no-recap" in sys.argv: changes["recap"] = "off"
    if "--recap" in sys.argv: changes["recap"] = None
    try: data = prefs.save(changes) if changes else prefs.load()
    except OSError as e: sys.exit("tokenwatch: cannot save settings to %s: %s" % (config.PREFS, e.strerror))
    print(f"🤖 saved settings: {prefs.describe(data)}\n   kept in {config.PREFS}")


def main():
    args.check(sys.argv)
    if "--save" in sys.argv: return save_settings()
    if "--no-recap" in sys.argv: sys.exit("tokenwatch: --no-recap only works with --save (turns the weekly recap off)")
    if "--recap" in sys.argv:
        print(recap.build() or "📅 tokenwatch: nothing spent last week")
        return
    frag, show = arg("--project"), int(arg("--sessions", 5))
    try: since, until = date_range(sys.argv)
    except (ValueError, IndexError):
        sys.exit("tokenwatch: --since/--until need a date like 2026-10-01")
    if "--export" in sys.argv or "--open" in sys.argv: return export(frag, since, until)
    rows = []
    for pdir in sorted(glob.glob(os.path.join(config.PROJECTS, "*"))):
        if not os.path.isdir(pdir): continue
        name = project_name(pdir)
        if frag and frag.lower() not in name.lower(): continue
        p = scan_project(pdir, since, until)
        if p["turns"] == 0: continue
        rows.append((p["cost"], name, p))
    rows.sort(key=lambda r: -r[0])
    if "--daily" in sys.argv:
        today = date.today()
        lo, hi = since or today - timedelta(days=13), until or today
        if lo > hi: sys.exit("tokenwatch: --since is after --until")
        mine = [scan_session(f) for d in glob.glob(os.path.join(config.PROJECTS, "*")) if os.path.isdir(d)
                and (not frag or frag.lower() in project_name(d).lower())
                for f in glob.glob(os.path.join(d, "*.jsonl"))]
        days = daily_totals(mine, lo, hi)
        if "--json" in sys.argv:
            print(json.dumps({"days": [{"date": d.isoformat(), "cost": round(c, 4)} for d, c in days],
                              "total_cost": round(sum(c for _, c in days), 4)}, indent=2))
        else:
            print("\n".join(trend_lines(days)))
            print(f"\n🤖 {len(days)} days: 🪙 ≈{money(sum(c for _, c in days))} at API list prices")
        return
    try: budget = parse_budget(sys.argv)
    except (ValueError, IndexError):
        sys.exit("tokenwatch: --budget needs a positive amount (e.g. --budget 20 --period week|day|month)")
    b = None
    if budget:
        lo, hi = period_range(budget[1])
        # a budget covers everything you spent, so ignore --project and the date filters here
        everything = [scan_session(f) for f in glob.glob(os.path.join(config.PROJECTS, "*", "*.jsonl"))]
        b = budget_status(spend_between(everything, lo, hi), *budget)
    if "--json" in sys.argv:
        print(json.dumps({"total_cost": round(sum(r[0] for r in rows), 4),
                          "total_tokens": sum(sum(r[2]["stats"].values()) for r in rows), "budget": b,
                          "projects": [project_summary(n, p, show) for _, n, p in rows]}, indent=2))
        return
    grand = burnt = 0
    for cost, name, p in rows:
        s = p["stats"]
        grand += cost; burnt += sum(s.values())
        print(f"\n🤖 ━━ {name}")
        print(f"   🪙 ≈{money(cost)} · 🔥 {fmt(sum(s.values()))} tokens burnt · {len(p['sessions'])} session(s) · {p['turns']} turns")
        print(f"   out {fmt(s['output_tokens'])} · in {fmt(s['input_tokens'])} · "
              f"cache w {fmt(s['cache_creation_input_tokens'])} / r {fmt(s['cache_read_input_tokens'])}")
        for t in advise(p): print(f"   {t}")
        done = sorted((x for x in p["sessions"] if x["turns"]), key=lambda x: x["start"], reverse=True)
        for x in done[:show]:
            sp = x["spent"]
            print(f"\n   ▸ {when(x['start'])} · 🪙 ≈{money(x['cost'])} · 🔥 {fmt(sum(x['tokens'].values()))} tokens · "
                  f"{x['turns']} turns · {nice(x['model'])}" + agents_note(x))
            print(f"     where it went: re-reading history {money(sp['read'])} · saving history {money(sp['write'])} · "
                  f"Claude's writing {money(sp['out'])} · new input {money(sp['in'])}")
            for t in session_tips(x) or ["✓ nothing to fix"]: print(f"     💡 {t}" if t[0] != "✓" else f"     😺 {t[2:]}")
        if len(done) > show: print(f"\n   (+{len(done) - show} older session(s): --sessions {len(done)})")
    if b: print(f"\n{budget_line(b)}")
    print(f"\n🤖 ═══ all projects: 🪙 ≈{money(grand)} at API list prices · 🔥 {fmt(burnt)} tokens burnt")
