"""Plain-English suggestions: the one-line live tip, per-session tips and project-wide advice."""
import re
from collections import defaultdict
from twlib.fmt import fmt, money, nice
from twlib.pricing import TOP_TIER, CHEAPER

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
