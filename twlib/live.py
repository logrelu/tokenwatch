"""Live-session state shared by statusline.py and pet.py: incremental transcript tailing, burn rate and Purr's mood."""
import json
from twlib.fmt import fmt, money
from twlib.pricing import KINDS, cost_of
from twlib.tips import top_tip
from twlib.usage import new_usage, context_of, plugin_hook

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
