#!/usr/bin/env python3
"""tokenwatch SessionStart hook: one short line about the previous session.
Deliberately tiny output — advice about token waste shouldn't waste tokens.
Optional: TOKENWATCH_BUDGET=20/week adds one budget line (nothing extra is printed without it)."""
import json, os, sys, glob
from tokenwatch import (fmt, money, scan_session, session_tips, parse_budget, period_range,
                        spend_between, budget_status, budget_line, PROJECTS)


def last_session_line(meta):
    tp = meta.get("transcript_path") or ""
    pdir = os.path.dirname(tp)
    if not pdir or not os.path.isdir(pdir): return None
    others = [f for f in glob.glob(os.path.join(pdir, "*.jsonl")) if f != tp]
    if not others: return None
    s = scan_session(max(others, key=os.path.getmtime))
    if s["turns"] == 0: return None
    tips = session_tips(s)
    more = f" (+{len(tips) - 1} more: python3 {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tokenwatch.py')})" if len(tips) > 1 else ""
    return (f"🤖 tokenwatch: last session cost ≈{money(s['cost'])} · 🔥 {fmt(sum(s['tokens'].values()))} tokens burnt · "
            f"{s['turns']} turns." + (f" 💡 {tips[0]}{more}" if tips else ""))


def budget_check():
    budget = parse_budget([])
    if not budget: return None
    lo, hi = period_range(budget[1])
    every = [scan_session(f) for f in glob.glob(os.path.join(PROJECTS, "*", "*.jsonl"))]
    return budget_line(budget_status(spend_between(every, lo, hi), *budget))


if __name__ == "__main__":
    try: meta = json.load(sys.stdin)
    except Exception: meta = {}
    for part in (last_session_line, budget_check):
        try:
            line = part(meta) if part is last_session_line else part()
        except Exception:
            line = None
        if line: print(line)
