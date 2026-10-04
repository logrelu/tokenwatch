#!/usr/bin/env python3
"""tokenwatch statusline for Claude Code: live session cost, tokens burnt + top tip.
Reads the statusline JSON on stdin, incrementally tails the transcript (state
cached in /tmp so each refresh only parses new lines). All local, no network."""
import json, os, sys, hashlib, time, shutil
from tokenwatch import fmt, money, top_tip, new_live_state, ingest, update_rate, mood_of

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
state = new_live_state()
try:
    old = json.load(open(state_file))
    if old.get("v") == 3 and old.get("offset", 0) <= os.path.getsize(tp): state.update(old)
except Exception:
    pass

with open(tp, errors="ignore") as f:
    f.seek(state["offset"])
    ingest(state, f)
idle = update_rate(state, now)
try: json.dump(state, open(state_file, "w"))
except Exception: pass

parts = [f"{E('🤖', '$')} {E('≈', '~')}{money(state['cost'])}", f"{E('🔥', 'tok')} {fmt(sum(state['sums'].values()))} tokens burnt", f"{state['turns']} turns"]
tip = top_tip(state["cost"], state["turns"], state["hook_runs"], state["context"], state["model"])
if tip: parts.append(f"{E('🙀', '!')} {tip}")
print(f" {DOT} ".join(parts))

mname, speech, _ = mood_of(state, idle, DOT)
mood, hot = {"HOT": (HOT, True), "SLEEPY": (SLEEPY, False), "FIRE": (FIRE, False),
             "WARMING": (WARMING, False), "CALM": (CALM, False)}[mname]
if cols >= 24: print(purr(mood, tick, speech, cols, hot))
