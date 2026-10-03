#!/usr/bin/env python3
"""tokenwatch SessionStart hook: one short line about the previous session.
Deliberately tiny output — advice about token waste shouldn't waste tokens."""
import json, os, sys, glob

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
pdir = os.path.dirname(tp)
if not pdir or not os.path.isdir(pdir): sys.exit(0)
others = [f for f in glob.glob(os.path.join(pdir, "*.jsonl")) if f != tp]
if not others: sys.exit(0)
last = max(others, key=os.path.getmtime)

sums = {k: 0 for k in WEIGHT}; turns = 0; marks = 0
for line in open(last, errors="ignore"):
    if "-plugin]" in line: marks += 1
    if '"usage"' not in line: continue
    try: u = (json.loads(line).get("message") or {}).get("usage")
    except Exception: continue
    if not u: continue
    turns += 1
    for k in WEIGHT: sums[k] += u.get(k, 0)
if turns == 0: sys.exit(0)
eq = sum(sums[k] * WEIGHT[k] for k in WEIGHT)
warn = " ⚠ plugin bloat: /plugins." if marks > 3 else (" ◦ long session; /clear between phases." if turns > 400 else "")
print(f"tokenwatch: last session ≈{fmt(eq)} eq tokens, {fmt(sums['output_tokens'])} out, {turns} turns.{warn}")
