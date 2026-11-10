---
description: Save a tokenwatch spending budget once (e.g. 25/week); used by the report, dashboard and greeting
argument-hint: "[AMOUNT/day|week|month | off]"
allowed-tools: Bash(python3:*)
---

Save or show my tokenwatch budget. The argument is: `$ARGUMENTS`

- If it is empty, run `python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --save` to show what is saved.
- If it is `off`, run `python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --budget off --save`.
- Otherwise it is an amount with an optional period, like `25/week`, `5/day`, `100/month` or `25`
  (a dollar sign is fine to drop). Run `python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --budget AMOUNT/PERIOD --save`,
  using `week` when no period is given. If it doesn't look like that, ask me for an amount instead of guessing.

Run it with Bash and show the output exactly as printed. Then, if a budget was saved, run
`python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --sessions 0` and show only its line starting with 💰.
