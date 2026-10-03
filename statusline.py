#!/usr/bin/env python3
"""tokenwatch statusline for Claude Code: live session spend + top warning.
Reads the statusline JSON on stdin, incrementally tails the transcript (state
cached in /tmp so each refresh only parses new lines). All local, no network."""
import json, os, sys, hashlib

WEIGHT = {"input_tokens": 1.0, "output_tokens": 5.0,
          "cache_creation_input_tokens": 1.25, "cache_read_input_tokens": 0.1}

def fmt(n):
    for u in ("", "K", "M", "B"):
        if abs(n) < 1000: return f"{n:,.0f}{u}"
        n /= 1000
    return f"{n:.1f}T"

try:
    meta = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tp = meta.get("transcript_path") or ""
model = ((meta.get("model") or {}).get("display_name")) or ""
if not tp or not os.path.exists(tp):
    print(f"🪙 {model} · no transcript yet"); sys.exit(0)

state_file = os.path.join("/tmp", "tokenwatch-" + hashlib.md5(tp.encode()).hexdigest()[:12] + ".json")
state = {"offset": 0, "sums": {k: 0 for k in WEIGHT}, "turns": 0, "plugin_marks": 0, "mcp_calls": 0}
try:
    old = json.load(open(state_file))
    if old.get("offset", 0) <= os.path.getsize(tp): state.update(old)
except Exception:
    pass

with open(tp, errors="ignore") as f:
    f.seek(state["offset"])
    for line in f:
        if "-plugin]" in line: state["plugin_marks"] += 1
        if '"mcp__' in line: state["mcp_calls"] += 1
        if '"usage"' not in line: continue
        try: u = (json.loads(line).get("message") or {}).get("usage")
        except Exception: continue
        if not u: continue
        state["turns"] += 1
        for k in WEIGHT: state["sums"][k] += u.get(k, 0)
    state["offset"] = f.tell()
try: json.dump(state, open(state_file, "w"))
except Exception: pass

eq = sum(state["sums"][k] * WEIGHT[k] for k in WEIGHT)
parts = [f"🪙 ≈{fmt(eq)} eq", f"↑{fmt(state['sums']['output_tokens'])} out", f"{state['turns']}t"]
if state["plugin_marks"] > 3: parts.append("⚠ plugin bloat (/plugins)")
elif state["turns"] > 400: parts.append("◦ long session (/clear?)")
print(" · ".join(parts))
