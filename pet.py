#!/usr/bin/env python3
"""tokenwatch live pet: Purr, a truly animated ASCII cat driven by your session's cost.
The statusline can't animate (Claude Code re-runs it at most once a second), so run
this in a second terminal pane/tab:  python3 pet.py [--project NAME] [--fps N]
It tails your newest transcript and redraws a 4-line block in place (~8 fps).
Try it with no session at all:      python3 pet.py --demo
Testing: --frames N prints N frames to stdout (no cursor tricks). All local, stdlib only."""
import os, sys, time, glob, shutil, signal
from tokenwatch import PROJECTS, KINDS, fmt, money, arg, new_live_state, ingest, update_rate, mood_of

try: sys.stdout.reconfigure(errors="replace")
except Exception: pass
UTF = (getattr(sys.stdout, "encoding", "") or "").lower().startswith("utf")
DOT = "·" if UTF else "-"
W = 9                      # sprite width
HEIGHT = 4                 # 3 cat lines + 1 HUD line
COLOUR = {"CALM": "32", "WARMING": "33", "FIRE": "31", "HOT": "35", "SLEEPY": "2"}
SPEED = {"CALM": 3.0, "WARMING": 9.0, "FIRE": 28.0, "HOT": 0.0, "SLEEPY": 0.0}  # cells per second
ORDER = ["CALM", "WARMING", "FIRE", "HOT", "SLEEPY"]
FLIP = str.maketrans("/\\()<>[]{}", "\\/)(><][}{")

def mirror(lines):
    return [l[::-1].translate(FLIP) for l in lines]

def walker(eyes, legs, tail_up, sweat=" "):
    """Right-facing cat (tail on the left): 3 lines, exactly W cols each."""
    l0 = list("  /\\_/\\  ")
    l1 = list(" ( " + eyes + " ) ")
    l2 = [" "] * W
    l2[1:8] = legs
    l1[8] = sweat
    (l1 if tail_up else l2)[0] = "~"
    return ["".join(l0), "".join(l1), "".join(l2)]

LEGS = ['(")_(")', '(_)_(")', '(")_(")', '(")_(_)']
SPRINT = ['(>)_(<)', '(<)_(>)']

def sprite(mood, f):
    """-> (lines, mirrorable). f is the frame counter."""
    if mood == "CALM":
        blink = f % 37 < 2
        return walker("-.-" if blink else "^.^", LEGS[(f // 2) % 4], (f // 6) % 2 == 0), True
    if mood == "WARMING":
        return walker("o.o" if (f // 4) % 2 else "^.^", LEGS[f % 4], f % 2 == 0, ";" if (f // 3) % 2 else " "), True
    if mood == "FIRE":
        return walker(">.<" if f % 2 else ">o<", SPRINT[f % 2], f % 2 == 0), True
    if mood == "HOT":
        l = ["  /\\_/\\  ", " ( " + ("@.@" if (f // 3) % 2 else "x.x") + " ) ", " (\")_(\") "]
        s = list(l[0])
        k = (f // 2) % 3                       # steam puffs drift off the ears
        s[[0, 1, 0][k]], s[[8, 7, 7][k]] = "'", "`"
        l[0] = "".join(s)
        return l, False
    breathe = (f // 5) % 2
    return ["         ", "  _.--._ " if breathe else "  .-==-. ", "(_(-.-)_) "[:W]], False

def shake(f):
    return (-1, 0, 1, 0)[f % 4]

class Pet:
    def __init__(self): self.x, self.dir = 0.0, 1
    def step(self, mood, dt, cols):
        hi = max(0, cols - 1 - W)
        self.x += self.dir * SPEED[mood] * dt
        while self.x > hi or self.x < 0:        # bounce off the walls
            self.x, self.dir = (2 * hi - self.x, -1) if self.x > hi else (-self.x, 1)
            if hi == 0: self.x = 0.0; break

def compose(mood, f, pet, cols):
    """Draw the cat + effects onto a 3 x cols grid of (char, colour) cells."""
    grid = [[(" ", "")] * cols for _ in range(3)]
    def put(r, c, ch, col):
        if 0 <= c < cols - 1 and ch != " ": grid[r][c] = (ch, col)
    lines, mirrorable = sprite(mood, f)
    if mirrorable and pet.dir < 0: lines = mirror(lines)
    hi = max(0, cols - 1 - W)
    x = int(round(pet.x))
    if mood == "HOT": x = min(max(x + shake(f), 0), hi)
    if mood == "SLEEPY": x = min(x, max(0, cols - 1 - W - 4))
    col = COLOUR[mood]
    for r, ln in enumerate(lines):
        for i, ch in enumerate(ln): put(r, x + i, ch, col)
    if mood == "FIRE":                           # flame trail behind the sprint
        for i in range(1, 7):
            c = x - i if pet.dir > 0 else x + W - 1 + i
            put(1, c, "*+'`. "[min(i - 1, 5)] if (f + i) % 4 else "*", "33" if i % 2 else "31")
            if (f + i) % 3 == 0: put(0 if i % 2 else 2, c, ".'`,"[(f + i) % 4], "31")
    elif mood == "SLEEPY":                       # z's float up and away
        for k in range(3):
            age = (f // 2 + k * 2) % 6
            put(2 - age // 2, x + W + age, "z" if age < 3 else "Z", "2")
    return grid

def paint(grid, color):
    out = []
    for row in grid:
        s, cur = "", ""
        end = len(row)
        while end and row[end - 1][0] == " ": end -= 1
        for ch, c in row[:end]:
            if color and c != cur: s += "\033[0m" + (f"\033[{c}m" if c else ""); cur = c
            s += ch
        out.append(s + "\033[0m" if color and end else s)
    return out

def hud(state, mood, speech, rate, cols, color):
    plain = f"{money(state['cost'])} {DOT} {fmt(sum(state['sums'].values()))} tokens {DOT} {state['turns']} turns {DOT} "
    if "/min" not in speech: plain += f"{money(rate)}/min {DOT} "   # calm/warming/fire speech already carries it
    plain = plain[:cols - 1]
    room = cols - 1 - len(plain)
    sp = speech[:max(0, room)]
    if not color: return plain + sp
    return f"\033[2m{plain}\033[0m\033[{COLOUR[mood]}m{sp}\033[0m"

def frame_lines(state, idle, pet, f, cols, color, mood=None):
    m, speech, _ = mood_of(state, idle, DOT)
    mood = mood or m
    return paint(compose(mood, f, pet, cols), color) + [hud(state, mood, speech, state["rate"], cols, color)], mood

# ---- data sources -------------------------------------------------------
def newest_transcript(frag):
    best, bt = None, -1.0
    for p in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl")):
        d = os.path.basename(os.path.dirname(p)).lower()
        if frag and frag.lower() not in d and frag.lower().replace("/", "-") not in d: continue
        try: t = os.path.getmtime(p)
        except OSError: continue
        if t > bt: best, bt = p, t
    return best

class Live:
    """Follows the newest transcript, re-picking when a newer one shows up."""
    def __init__(self, frag):
        self.frag, self.path, self.state, self.idle, self.last_poll = frag, None, new_live_state(), 0.0, 0.0
    def poll(self, now):
        if self.path and now - self.last_poll < 1.0: return
        self.last_poll = now
        p = newest_transcript(self.frag)
        if p and p != self.path:                 # new session: start over
            self.path, self.state = p, new_live_state()
            with open(p, errors="ignore") as f: ingest(self.state, f)
            s = self.state
            s["prev_cost"], s["t_last"] = s["cost"], now
            try: s["t_active"] = os.path.getmtime(p)
            except OSError: s["t_active"] = now
        elif p:
            try:
                if os.path.getsize(p) < self.state["offset"]: self.state = new_live_state()
                with open(p, errors="ignore") as f:
                    f.seek(self.state["offset"]); ingest(self.state, f)
            except OSError: pass
        self.idle = update_rate(self.state, now) if self.path else 0.0
        if self.path is None: self.idle = 0.0

def demo_state(mood):
    s = new_live_state()
    s.update(turns=14, cost=1.37, model="claude-sonnet-5-5", context=40_000, rate=0.04,
             sums={k: v for k, v in zip(KINDS, (2_000, 30_000, 120_000, 900_000))})
    idle = 5.0
    if mood == "WARMING": s.update(rate=0.22, context=120_000, cost=3.1)
    elif mood == "FIRE": s.update(rate=0.85, context=90_000, cost=6.4, turns=31)
    elif mood == "HOT": s.update(context=230_000, rate=0.30, cost=9.2, turns=60)
    elif mood == "SLEEPY": idle = 720.0
    return s, idle

# ---- main ---------------------------------------------------------------
def main():
    demo, fps = "--demo" in sys.argv, min(30.0, max(1.0, float(arg("--fps", 8))))
    nframes = int(arg("--frames", 0))
    tty = sys.stdout.isatty()
    color = os.environ.get("NO_COLOR") is None and os.environ.get("TOKENWATCH_COLOR") != "0" \
        and (tty or os.environ.get("TOKENWATCH_COLOR") == "1")
    live = None if demo else Live(arg("--project"))
    pet, dt = Pet(), 1.0 / fps
    t0 = float(os.environ.get("TOKENWATCH_NOW") or time.time())   # env override: testing only
    cols_now = lambda: int(os.environ.get("COLUMNS") or shutil.get_terminal_size((80, 24)).columns)

    def build(f, t):
        cols = max(cols_now(), 12)
        if demo:
            mood = ORDER[int((t - t0) // 4) % len(ORDER)]
            state, idle = demo_state(mood)
        else:
            live.poll(t); state, idle = live.state, live.idle
            mood = None
        lines, mood = frame_lines(state, idle, pet, f, cols, color, mood)
        pet.step(mood, dt, cols)
        return lines

    if nframes:                                   # test mode: virtual clock, plain stdout
        for f in range(nframes):
            print("\n".join(build(f, t0 + f * dt)) + "\n")
        return
    if not tty:                                   # piped: one frame, done
        print("\n".join(build(0, t0)))
        return

    def bye(*_): sys.exit(0)
    signal.signal(signal.SIGTERM, bye)
    out = sys.stdout
    out.write("\033[?25l" + "\n" * HEIGHT); out.flush()    # hide cursor, reserve the block
    try:
        start, f = time.time(), 0
        while True:
            t = t0 + (time.time() - start)
            body = "".join("\033[2K\r" + l + "\n" for l in build(f, t))
            out.write(f"\033[{HEIGHT}A" + body); out.flush()
            f += 1
            time.sleep(max(0.0, start + f * dt - time.time()))
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        out.write("\033[0m\033[?25h"); out.flush()

if __name__ == "__main__":
    main()
