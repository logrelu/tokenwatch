#!/usr/bin/env python3
"""tokenwatch statusline for Claude Code: live session cost, tokens burnt + top tip.
Reads the statusline JSON on stdin, incrementally tails the transcript (state
cached in /tmp so each refresh only parses new lines). All local, no network."""
import json, os, sys, hashlib, time, shutil
from tokenwatch import KINDS, fmt, money, cost_of, new_usage, context_of, top_tip, plugin_hook

try: sys.stdout.reconfigure(errors="replace")
except Exception: pass
UTF = (getattr(sys.stdout, "encoding", "") or "").lower().startswith("utf")
E = (lambda a, b: a) if UTF else (lambda a, b: b)
DOT = E("·", "-")
TICK = 2
# mood: (frames, patrol speed, ANSI colour); frames are written tail-left "~face"
CALM = (["~(=^.^=)", "~(=^.^=)", "~(=-.-=)"], 1, "32")
WARMING = (["~(=^.^;)", "~(=^o^;)"], 2, "33")
FIRE = (["~(=>.<=)*", "~(=>o<=)!"], 3, "31")
HOT = (["(=@_@=)$", "(=x_x=) $"], 0, "35")
SLEEPY = (["(=-.-=)z", "(=-.-=)zZ", "(=-.-=)zZz"], 0, "2")

def purr(mood, tick, speech, cols, hot=False):
    """Line 2: the cat patrols a 12-col track; returns the string to print."""
    frames, speed, colour = mood
    R = 12 if cols >= 60 else 0
    frame = frames[tick % len(frames)]
    right = True
    if hot: pos = tick % 2 if R else 0
    elif speed and R:
        p = (tick * speed) % (2 * R)
        pos, right = (p, True) if p < R else (2 * R - p, False)
    else: pos = 0
    if not right and frame.startswith("~"): frame = frame[1:] + "~"
    sprite = frame.ljust(10)
    plain = " " * pos + sprite + ("  " + speech if cols >= 40 else "")
    plain = plain[:cols - 1]
    a, b = pos, pos + len(frame)
    if os.environ.get("NO_COLOR") is None and os.environ.get("TOKENWATCH_COLOR") != "0":
        return plain[:a] + f"\033[{colour}m" + plain[a:b] + "\033[0m" + plain[b:]
    return plain

now = float(os.environ.get("TOKENWATCH_NOW") or time.time())  # env override: testing only
tick = int(now // TICK)
cols = int(os.environ.get("COLUMNS") or shutil.get_terminal_size((80, 24)).columns)

try:
    meta = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tp = meta.get("transcript_path") or ""
model = ((meta.get("model") or {}).get("display_name")) or ""
if not tp or not os.path.exists(tp):
    print(f"{E('🪙', '$')} {model} {DOT} no transcript yet")
    if cols >= 24: print(purr(SLEEPY, 0, "waiting for a chat", cols))
    sys.exit(0)

state_file = os.path.join("/tmp", "tokenwatch-" + hashlib.md5(tp.encode()).hexdigest()[:12] + ".json")
state = {"v": 3, "offset": 0, "sums": {k: 0 for k in KINDS}, "cost": 0.0, "turns": 0,
         "hook_runs": 0, "seen": [], "context": 0, "model": "", "t_last": 0.0, "t_active": 0.0, "prev_cost": 0.0, "rate": 0.0}
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
dt = now - (state["t_last"] or now); dc = state["cost"] - state["prev_cost"]
if dc > 0: state["t_active"] = now
inst = dc / dt * 60 if dt > 0 else 0.0  # $/min
if dt > 600 or state["t_last"] == 0: state["rate"] = inst
elif dt > 0: state["rate"] += min(1.0, dt / 120) * (inst - state["rate"])
state["t_last"], state["prev_cost"] = now, state["cost"]
idle = max(0.0, now - (state["t_active"] or now))
try: json.dump(state, open(state_file, "w"))
except Exception: pass

parts = [f"{E('🤖', '$')} {E('≈', '~')}{money(state['cost'])}", f"{E('🔥', 'tok')} {fmt(sum(state['sums'].values()))} tokens burnt", f"{state['turns']} turns"]
tip = top_tip(state["cost"], state["turns"], state["hook_runs"], state["context"], state["model"])
if tip: parts.append(f"{E('🙀', '!')} {tip}")
print(f" {DOT} ".join(parts))

ctx, rate, turns = state["context"], state["rate"], state["turns"]
if ctx > 200_000 or tip:
    mood, hot = HOT, True
    speech = f"{fmt(ctx)} to re-read: /compact" if ctx > 200_000 else "hot paws, see tip above"
elif turns == 0 or idle > 300:
    mood, hot = SLEEPY, False
    speech = "waiting for a chat" if turns == 0 else f"napping {DOT} idle {int(idle // 60)}m"
elif rate >= 0.50: mood, hot, speech = FIRE, False, f"zoomies! {money(rate)}/min"
elif rate >= 0.10 or ctx >= 100_000: mood, hot, speech = WARMING, False, f"warming up {DOT} {money(rate)}/min"
else: mood, hot, speech = CALM, False, f"purring along {DOT} {money(rate)}/min"
if cols >= 24: print(purr(mood, tick, speech, cols, hot))
