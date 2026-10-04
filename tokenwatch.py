#!/usr/bin/env python3
"""tokenwatch — reads your local Claude Code transcripts and tells you where tokens go.

Everything is local: ~/.claude/projects/**/*.jsonl never leaves this machine.
Run: python3 tokenwatch.py [--project <name-fragment>] [--sessions <how many per project>]
"""
import json, glob, os, re, sys
from collections import defaultdict
from datetime import datetime

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")

KINDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")

# USD per million tokens: (input, output, cache read). Public API list prices, 2026-09.
# Matched by prefix, most specific first. Good enough for "where does it go", not for invoicing —
# and on a Pro/Max subscription you don't pay per token at all; read it as how fast you use your limit.
PRICES = [
    ("claude-fable-5-1",  (10.0, 50.0, 0.25)),
    ("claude-mythos-5-1", (10.0, 50.0, 0.25)),
    ("claude-fable",      (10.0, 50.0, 1.00)),
    ("claude-mythos",     (10.0, 50.0, 1.00)),
    ("claude-opus-5-5",   (4.0, 20.0, 0.20)),
    ("claude-opus",       (5.0, 25.0, 0.50)),
    ("claude-sonnet-5",   (2.0, 10.0, 0.20)),
    ("claude-sonnet",     (3.0, 15.0, 0.30)),
    ("claude-haiku",      (1.0, 5.0, 0.10)),
]
# Cache writes cost more than plain input: 1.25x for the 5-minute cache, 2x for the 1-hour cache.
WRITE_5M, WRITE_1H = 1.25, 2.0
TOP_TIER = ("claude-fable", "claude-mythos", "claude-opus")
CHEAPER = "claude-sonnet-5-5"       # what the "same work on a cheaper model" figure is priced at

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

def cost_parts(model, u):
    """Dollar cost of one reply by token kind, at list prices; all zero for models we don't know."""
    for prefix, (p_in, p_out, p_read) in PRICES:
        if (model or "").startswith(prefix): break
    else:
        p_in = p_out = p_read = 0.0
    w = u.get("cache_creation_input_tokens", 0)
    w1h = min(w, (u.get("cache_creation") or {}).get("ephemeral_1h_input_tokens", 0))
    return {"in": u.get("input_tokens", 0) * p_in / 1e6,
            "out": u.get("output_tokens", 0) * p_out / 1e6,
            "write": ((w - w1h) * WRITE_5M + w1h * WRITE_1H) * p_in / 1e6,
            "read": u.get("cache_read_input_tokens", 0) * p_read / 1e6}

def cost_of(model, u):
    return sum(cost_parts(model, u).values())

def new_usage(msg, seen):
    """The usage of a reply not counted yet, else None. Claude Code writes one transcript line
    per content block and repeats the reply's usage on each, so every reply is counted once by id.
    A reply's lines sit together, so `seen` only needs to remember recent ids."""
    u, mid = msg.get("usage"), msg.get("id")
    if not u or (mid and mid in seen): return None
    if mid:
        seen.append(mid)
        if len(seen) > 100: del seen[:-50]
    return u

def context_of(u):
    """How many tokens of conversation the model had to read for this reply."""
    return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)

PLUGIN_MARK = re.compile(r"\[([\w-]+-plugin)\]")

def plugin_hook(line):
    """(runs, seconds, characters added to the chat, plugin names) if this transcript line records
    a plugin hook, else None. Only real hook records count, so a chat that merely talks about a
    plugin doesn't look like bloat. `content` is what reached the model (big output is truncated)."""
    if '"attachment"' not in line or ("CLAUDE_PLUGIN_ROOT" not in line and '"hook_additional_context"' not in line):
        return None
    try: a = json.loads(line).get("attachment") or {}
    except Exception: return None
    kind, content = a.get("type") or "", a.get("content") or ""
    if not isinstance(content, str): content = "\n".join(map(str, content))
    names = PLUGIN_MARK.findall(content)
    if kind == "hook_additional_context":
        return (0, 0.0, len(content), names) if names else None
    if kind.startswith("hook_") and "CLAUDE_PLUGIN_ROOT" in (a.get("command") or ""):
        try: secs = float(a.get("durationMs") or 0) / 1000
        except ValueError: secs = 0.0
        return (1, secs, len(content), names)
    return None

def top_tip(cost, turns, hook_runs, context, model):
    """The single most useful suggestion for the live session, kept short ('' if all is well)."""
    if context > 200_000:
        return f"this chat re-reads {fmt(context)} tokens of history on every step: /compact, or /clear for a new task"
    if hook_runs > 50:
        return f"plugin hooks ran {hook_runs}x in this chat: if this project doesn't need the plugin, /plugins"
    if turns > 400:
        return "very long chat: /clear when you switch to an unrelated task"
    if cost > 5 and (model or "").startswith(TOP_TIER):
        return "top-tier model in use: /model sonnet handles routine work for a fraction of the cost"
    return ""

# --- live session helpers, shared by statusline.py and pet.py ---
def new_live_state():
    return {"v": 3, "offset": 0, "sums": {k: 0 for k in KINDS}, "cost": 0.0, "turns": 0,
            "hook_runs": 0, "seen": [], "context": 0, "model": "", "t_last": 0.0, "t_active": 0.0, "prev_cost": 0.0, "rate": 0.0}

def ingest(state, f):
    """Parse the transcript lines from f's current position into state (incremental)."""
    for line in f:
        h = plugin_hook(line)
        if h: state["hook_runs"] += h[0]; continue
        if '"usage"' not in line: continue
        try: msg = json.loads(line).get("message") or {}
        except Exception: continue
        u = new_usage(msg, state["seen"])
        if not u: continue
        state["turns"] += 1
        state["cost"] += cost_of(msg.get("model"), u)
        state["context"] = context_of(u)
        if (msg.get("model") or "").startswith("claude"): state["model"] = msg["model"]
        for k in KINDS: state["sums"][k] += u.get(k, 0)
    state["offset"] = f.tell()

def update_rate(state, now):
    """Smoothed $/min; returns seconds idle (since cost last grew)."""
    dt = now - (state["t_last"] or now); dc = state["cost"] - state["prev_cost"]
    if dc > 0: state["t_active"] = now
    inst = dc / dt * 60 if dt > 0 else 0.0
    if dt > 600 or state["t_last"] == 0: state["rate"] = inst
    elif dt > 0: state["rate"] += min(1.0, dt / 120) * (inst - state["rate"])
    state["t_last"], state["prev_cost"] = now, state["cost"]
    return max(0.0, now - (state["t_active"] or now))

def mood_of(state, idle, dot="·"):
    """-> (mood, speech, tip); mood is one of HOT, SLEEPY, FIRE, WARMING, CALM."""
    ctx, rate, turns = state["context"], state["rate"], state["turns"]
    tip = top_tip(state["cost"], turns, state["hook_runs"], ctx, state["model"])
    if ctx > 200_000 or tip:
        return "HOT", (f"{fmt(ctx)} to re-read: /compact" if ctx > 200_000 else "hot paws, see tip above"), tip
    if turns == 0 or idle > 300:
        return "SLEEPY", ("waiting for a chat" if turns == 0 else f"napping {dot} idle {int(idle // 60)}m"), tip
    if rate >= 0.50: return "FIRE", f"zoomies! {money(rate)}/min", tip
    if rate >= 0.10 or ctx >= 100_000: return "WARMING", f"warming up {dot} {money(rate)}/min", tip
    return "CALM", f"purring along {dot} {money(rate)}/min", tip

def scan_session(f):
    """Everything tokenwatch knows about one session transcript."""
    s = dict(file=f, start="", turns=0, cost=0.0, tokens={k: 0 for k in KINDS},
             spent={"read": 0.0, "write": 0.0, "out": 0.0, "in": 0.0}, as_cheaper=0.0,
             peak=0, context=0, first_write=0, model="", rebuilds=0, rebuild_cost=0.0,
             hook_runs=0, hook_secs=0.0, hook_chars=0, plugins=set(), bash=[], mcp=defaultdict(int))
    seen = []
    for line in open(f, errors="ignore"):
        h = plugin_hook(line)
        if h:
            s["hook_runs"] += h[0]; s["hook_secs"] += h[1]; s["hook_chars"] += h[2]; s["plugins"].update(h[3])
            continue
        try: d = json.loads(line)
        except Exception: continue
        if not s["start"]: s["start"] = d.get("timestamp") or ""
        msg = d.get("message") or {}
        u = new_usage(msg, seen)
        if u:
            model = msg.get("model") or ""
            parts = cost_parts(model, u)
            s["turns"] += 1
            s["cost"] += sum(parts.values())
            s["as_cheaper"] += cost_of(CHEAPER, u)
            for k in parts: s["spent"][k] += parts[k]
            for k in KINDS: s["tokens"][k] += u.get(k, 0)
            if model.startswith("claude"): s["model"] = model
            s["context"] = context_of(u); s["peak"] = max(s["peak"], s["context"])
            w = u.get("cache_creation_input_tokens", 0)
            if s["turns"] == 1:
                s["first_write"] = w
            elif w > 50_000 and w > 0.5 * s["context"]:
                # most of the conversation written to cache again: the saved copy had expired
                s["rebuilds"] += 1; s["rebuild_cost"] += parts["write"]
        for c in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                name = c.get("name", "")
                if name.startswith("mcp__"):
                    s["mcp"][name.split("__")[1]] += 1
                elif name == "Bash":
                    s["bash"].append((c.get("input") or {}).get("command", "")[:200])
    return s

def session_tips(s):
    """Every suggestion for one session, biggest saving first, each with the numbers behind it."""
    out = []
    cost, spent = s["cost"], s["spent"]
    if cost >= 1 and spent["read"] > 0.4 * cost and s["peak"] > 150_000:
        out.append(f"long chat: {spent['read'] / cost:.0%} of the cost ({money(spent['read'])}) was Claude re-reading the "
                   f"conversation, up to {fmt(s['peak'])} tokens on every step. /clear when you switch tasks, "
                   f"/compact inside a long one.")
    if s["rebuilds"] >= 2 and s["rebuild_cost"] >= 1:
        out.append(f"cold restarts: {s['rebuilds']} times the whole conversation had to be saved again "
                   f"(≈{money(s['rebuild_cost'])}), usually after a break of an hour or more. After a long break, "
                   f"/clear and start fresh rather than continuing a huge chat.")
    if s["hook_runs"] > 20:
        who = ", ".join(sorted(s["plugins"])) or "a plugin"
        secs = s["hook_secs"]
        took = f"{secs / 60:.0f} min" if secs >= 90 else f"{secs:.0f}s"
        out.append(f"plugin hooks ({who}) ran {s['hook_runs']} times, ≈{took} of hook time, and added "
                   f"≈{fmt(s['hook_chars'] / 4)} tokens to the chat. If this project doesn't use that plugin, "
                   f"turn it off in /plugins.")
    if cost > 5 and s["model"].startswith(TOP_TIER) and s["as_cheaper"] < 0.7 * cost:
        out.append(f"model: this ran on {nice(s['model'])}. The same tokens at {nice(CHEAPER)} prices come to "
                   f"≈{money(s['as_cheaper'])}: /model sonnet for routine work.")
    return out

def scan_project(pdir):
    sessions = [scan_session(f) for f in sorted(glob.glob(os.path.join(pdir, "*.jsonl")))]
    stats = {k: sum(s["tokens"][k] for s in sessions) for k in KINDS}
    mcp = defaultdict(int)
    for s in sessions:
        for k, v in s["mcp"].items(): mcp[k] += v
    return dict(sessions=sessions, stats=stats, cost=sum(s["cost"] for s in sessions),
                turns=sum(s["turns"] for s in sessions), mcp=mcp,
                bash=[c for s in sessions for c in s["bash"]])

def advise(p):
    """Project-wide suggestions (per-session ones come from session_tips)."""
    out = []
    # 1. Heavy session start = plugin/MCP/CLAUDE.md baggage re-cached every session
    heavy = [s["first_write"] for s in p["sessions"] if s["first_write"] > 40_000]
    if heavy:
        out.append(f"⚠ heavy session start: ~{fmt(sum(heavy)/len(heavy))} tokens of context are loaded before any work "
                   f"happens. That's tool lists, connectors, plugins and CLAUDE.md. Prune what this project doesn't use.")
    # 2. Repeated CLI patterns an integration would do better
    counts = defaultdict(int)
    for c in p["bash"]:
        for tool, hint in [("gh ", "GitHub MCP server or gh extensions"),
                           ("curl ", "a dedicated MCP/connector for that API"),
                           ("psql", "a database MCP server"), ("aws ", "an AWS MCP server")]:
            if re.search(r"(^|[;&|]\s*)" + re.escape(tool), c): counts[(tool.strip(), hint)] += 1
    for (tool, hint), n in sorted(counts.items(), key=lambda x: -x[1]):
        if n >= 15:
            out.append(f"◦ `{tool}` ran {n}x in Bash: heavy manual use — {hint} could make this cheaper and less error-prone.")
    # 3. MCP servers connected vs actually used (visible side only: calls)
    if p["mcp"]:
        used = ", ".join(f"{k} ({v}x)" for k, v in sorted(p["mcp"].items(), key=lambda x: -x[1]))
        out.append(f"◦ MCP actually used here: {used}. Any other connected server is pure context overhead for this project.")
    else:
        out.append("◦ no MCP tools were ever called in this project — every connected server's tool list is dead weight here.")
    return out

def arg(flag, default=None):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default

def main():
    frag, show = arg("--project"), int(arg("--sessions", 5))
    rows = []
    for pdir in sorted(glob.glob(os.path.join(PROJECTS, "*"))):
        if not os.path.isdir(pdir): continue
        name = os.path.basename(pdir).replace("-Users-" + os.path.basename(HOME) + "-", "~/").replace("-", "/")
        if frag and frag.lower() not in name.lower(): continue
        p = scan_project(pdir)
        if p["turns"] == 0: continue
        rows.append((p["cost"], name, p))
    rows.sort(key=lambda r: -r[0])
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
                  f"{x['turns']} turns · {nice(x['model'])}")
            print(f"     where it went: re-reading history {money(sp['read'])} · saving history {money(sp['write'])} · "
                  f"Claude's writing {money(sp['out'])} · new input {money(sp['in'])}")
            for t in session_tips(x) or ["✓ nothing to fix"]: print(f"     💡 {t}" if t[0] != "✓" else f"     😺 {t[2:]}")
        if len(done) > show: print(f"\n   (+{len(done) - show} older session(s): --sessions {len(done)})")
    print(f"\n🤖 ═══ all projects: 🪙 ≈{money(grand)} at API list prices · 🔥 {fmt(burnt)} tokens burnt")

if __name__ == "__main__":
    main()
