#!/usr/bin/env python3
"""tokenwatch — reads your local Claude Code transcripts and tells you where tokens go.

Everything is local: ~/.claude/projects/**/*.jsonl never leaves this machine.
Run: python3 tokenwatch.py [--project <name-fragment>]
"""
import json, glob, os, re, sys
from collections import defaultdict

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")

# Relative price weights (approximate, provider-typical): what a token of each kind
# costs compared to a fresh input token. Good enough for ranking, not for invoicing.
WEIGHT = {"input_tokens": 1.0, "output_tokens": 5.0,
          "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1}

def fmt(n):
    for unit in ("", "K", "M", "B"):
        if abs(n) < 1000: return f"{n:,.0f}{unit}"
        n /= 1000
    return f"{n:.1f}T"

def scan_project(pdir):
    stats = {k: 0 for k in WEIGHT}
    turns = sessions = 0
    first_turn_writes = []          # cache_creation of each session's first assistant turn
    bash_cmds = []
    mcp_calls = defaultdict(int)    # server -> calls
    plugin_hits = defaultdict(int)  # plugin/hook text markers seen
    per_session = {}
    marker = re.compile(r"\[([\w-]+-plugin)\]")
    for f in sorted(glob.glob(os.path.join(pdir, "*.jsonl"))):
        sessions += 1
        s_use = {k: 0 for k in WEIGHT}; s_turns = 0; first = True
        for line in open(f, errors="ignore"):
            for m in marker.findall(line):
                plugin_hits[m] += 1
            try: d = json.loads(line)
            except Exception: continue
            msg = d.get("message") or {}
            u = msg.get("usage")
            if u:
                turns += 1; s_turns += 1
                for k in WEIGHT:
                    stats[k] += u.get(k, 0); s_use[k] += u.get(k, 0)
                if first:
                    first_turn_writes.append(u.get("cache_creation_input_tokens", 0)); first = False
            for c in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    name = c.get("name", "")
                    if name.startswith("mcp__"):
                        mcp_calls[name.split("__")[1]] += 1
                    elif name == "Bash":
                        cmd = (c.get("input") or {}).get("command", "")[:200]
                        bash_cmds.append(cmd)
        per_session[os.path.basename(f)] = (s_turns, s_use)
    return dict(stats=stats, turns=turns, sessions=sessions, first_turn_writes=first_turn_writes,
                bash=bash_cmds, mcp=mcp_calls, plugins=plugin_hits, per_session=per_session)

def advise(name, p):
    out = []
    w = sum(p["stats"][k] * WEIGHT[k] for k in WEIGHT)
    # 1. Heavy session start = plugin/MCP/CLAUDE.md baggage re-cached every session
    heavy = [x for x in p["first_turn_writes"] if x > 40_000]
    if heavy:
        out.append(f"⚠ heavy session start: first turn writes ~{fmt(sum(heavy)/len(heavy))} tokens of context "
                   f"before any work happens. That's plugins, MCP tool lists and hooks. Prune what this project doesn't use.")
    # 2. Plugin noise: a plugin injecting itself often is a cost even if you never notice it
    for plug, hits in p["plugins"].items():
        if hits > 3:
            out.append(f"⚠ {plug}: injected itself ~{hits}x into this project's sessions. If this project "
                       f"doesn't use it, disable it (/plugins) — it rides along in every cache write.")
    # 3. Marathon sessions
    for sess, (t, su) in p["per_session"].items():
        if t > 400:
            reads = su["cache_read_input_tokens"]
            out.append(f"◦ marathon session ({t} turns, {fmt(reads)} cache reads): fine if the context mattered "
                       f"throughout; /clear between unrelated phases would have cut re-reading.")
    # 4. Repeated CLI patterns an integration would do better
    counts = defaultdict(int)
    for c in p["bash"]:
        for tool, hint in [("gh ", "GitHub MCP server or gh extensions"),
                           ("curl ", "a dedicated MCP/connector for that API"),
                           ("psql", "a database MCP server"), ("aws ", "an AWS MCP server")]:
            if re.search(r"(^|[;&|]\s*)" + re.escape(tool), c): counts[(tool.strip(), hint)] += 1
    for (tool, hint), n in sorted(counts.items(), key=lambda x: -x[1]):
        if n >= 15:
            out.append(f"◦ `{tool}` ran {n}x in Bash: heavy manual use — {hint} could make this cheaper and less error-prone.")
    # 5. MCP servers connected vs actually used (visible side only: calls)
    if p["mcp"]:
        used = ", ".join(f"{k} ({v}x)" for k, v in sorted(p["mcp"].items(), key=lambda x: -x[1]))
        out.append(f"◦ MCP actually used here: {used}. Any other connected server is pure context overhead for this project.")
    else:
        out.append("◦ no MCP tools were ever called in this project — every connected server's tool list is dead weight here.")
    return w, out

def main():
    frag = sys.argv[sys.argv.index("--project") + 1] if "--project" in sys.argv else None
    rows = []
    for pdir in sorted(glob.glob(os.path.join(PROJECTS, "*"))):
        if not os.path.isdir(pdir): continue
        name = os.path.basename(pdir).replace("-Users-" + os.path.basename(HOME) + "-", "~/").replace("-", "/")
        if frag and frag.lower() not in name.lower(): continue
        p = scan_project(pdir)
        if p["turns"] == 0: continue
        w, tips = advise(name, p)
        rows.append((w, name, p, tips))
    rows.sort(reverse=True)
    grand = 0
    for w, name, p, tips in rows:
        grand += w
        s = p["stats"]
        print(f"\n━━ {name}")
        print(f"   {p['sessions']} session(s) · {p['turns']} turns · out {fmt(s['output_tokens'])} · "
              f"in {fmt(s['input_tokens'])} · cache w {fmt(s['cache_creation_input_tokens'])} / r {fmt(s['cache_read_input_tokens'])}"
              f" · weighted ≈ {fmt(w)} input-equivalent tokens")
        for t in tips: print(f"   {t}")
    print(f"\n═══ all projects, weighted total ≈ {fmt(grand)} input-equivalent tokens")

if __name__ == "__main__":
    main()
