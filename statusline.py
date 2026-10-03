#!/usr/bin/env python3
"""tokenwatch statusline for Claude Code: live session cost, tokens burnt + top tip.
Reads the statusline JSON on stdin, incrementally tails the transcript (state
cached in /tmp so each refresh only parses new lines). All local, no network."""
import json, os, sys, hashlib
from tokenwatch import KINDS, fmt, money, cost_of, new_usage, context_of, top_tip, plugin_hook

try:
    meta = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tp = meta.get("transcript_path") or ""
model = ((meta.get("model") or {}).get("display_name")) or ""
if not tp or not os.path.exists(tp):
    print(f"🪙 {model} · no transcript yet"); sys.exit(0)

state_file = os.path.join("/tmp", "tokenwatch-" + hashlib.md5(tp.encode()).hexdigest()[:12] + ".json")
state = {"v": 3, "offset": 0, "sums": {k: 0 for k in KINDS}, "cost": 0.0, "turns": 0,
         "hook_runs": 0, "seen": [], "context": 0, "model": ""}
try:
    old = json.load(open(state_file))
    if old.get("v") == 3 and old.get("offset", 0) <= os.path.getsize(tp): state.update(old)
except Exception:
    pass

with open(tp, errors="ignore") as f:
    f.seek(state["offset"])
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
try: json.dump(state, open(state_file, "w"))
except Exception: pass

parts = [f"🤖 ≈{money(state['cost'])}", f"🔥 {fmt(sum(state['sums'].values()))} tokens burnt", f"{state['turns']} turns"]
tip = top_tip(state["cost"], state["turns"], state["hook_runs"], state["context"], state["model"])
parts.append(f"🙀 {tip}" if tip else "😺 running lean")
print(" · ".join(parts))
