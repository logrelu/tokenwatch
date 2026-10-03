#!/usr/bin/env python3
"""tokenwatch SessionStart hook: one short line about the previous session.
Deliberately tiny output — advice about token waste shouldn't waste tokens."""
import json, os, sys, glob
from tokenwatch import fmt, money, scan_session, session_tips

try:
    meta = json.load(sys.stdin)
except Exception:
    sys.exit(0)
tp = meta.get("transcript_path") or ""
pdir = os.path.dirname(tp)
if not pdir or not os.path.isdir(pdir): sys.exit(0)
others = [f for f in glob.glob(os.path.join(pdir, "*.jsonl")) if f != tp]
if not others: sys.exit(0)

s = scan_session(max(others, key=os.path.getmtime))
if s["turns"] == 0: sys.exit(0)
tips = session_tips(s)
more = f" (+{len(tips) - 1} more: python3 {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tokenwatch.py')})" if len(tips) > 1 else ""
print(f"🤖 tokenwatch: last session cost ≈{money(s['cost'])} · 🔥 {fmt(sum(s['tokens'].values()))} tokens burnt · "
      f"{s['turns']} turns." + (f" 💡 {tips[0]}{more}" if tips else ""))
