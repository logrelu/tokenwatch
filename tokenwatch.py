#!/usr/bin/env python3
"""tokenwatch — reads your local Claude Code transcripts and tells you where tokens go.

Everything is local: ~/.claude/projects/**/*.jsonl never leaves this machine.
Run: python3 tokenwatch.py [--project <name-fragment>] [--sessions <how many per project>] [--json]
     [--today | --week | --since YYYY-MM-DD [--until YYYY-MM-DD]] [--daily]
"""
# Everything below is re-exported so `from tokenwatch import ...` keeps working (statusline.py, pet.py, tests).
from twlib.fmt import fmt, money, nice, when
from twlib.usage import new_usage, context_of, PLUGIN_MARK, plugin_hook
from twlib.pricing import KINDS, PRICES, WRITE_5M, WRITE_1H, TOP_TIER, CHEAPER, cost_parts, cost_of
from twlib.live import new_live_state, ingest, update_rate, mood_of
from twlib.tips import top_tip, session_tips, advise
from twlib.config import HOME, PROJECTS
from twlib.dates import session_date, date_range, PERIODS, period_range
from twlib.budget import parse_budget, spend_between, budget_status, budget_line
from twlib.trend import SPARK, sparkline, daily_totals, trend_lines
from twlib.scan import scan_session, scan_project, project_name
from twlib.report import session_summary, project_summary
from twlib.cli import arg, main


if __name__ == "__main__":
    main()
