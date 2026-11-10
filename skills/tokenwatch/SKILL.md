---
name: tokenwatch
description: Answer questions about the user's Claude Code spending and token use from their local transcripts. Use when they ask how much they spent or how many tokens they used (today, this week, this month, on a date, in a project), why a day or session was expensive, which project or session cost the most, whether they are on budget, how spending is trending, or how to use fewer tokens with Claude Code.
allowed-tools: Bash(python3:*)
---

# tokenwatch: answer spending questions in plain English

tokenwatch reads the Claude Code transcripts on this machine (read-only, no network). Run it with Bash,
then answer the question yourself in plain words. Never paste raw JSON or the whole report.

The script is `"${CLAUDE_PLUGIN_ROOT}/tokenwatch.py"`. Always use that exact path. Do not search for other copies.

## 1. Pick the flags from the question

| They ask about | Add |
|---|---|
| today | `--today` |
| this week, the last 7 days | `--week` |
| a date or range ("since Monday", "in October") | `--since YYYY-MM-DD [--until YYYY-MM-DD]` (work out the dates from today) |
| one project ("in myapp") | `--project NAME` |
| a trend, "every day", "is it going up" | `--daily` (combine with a date flag) |
| a budget | `--budget N/PERIOD` (period: day, week or month) only if they give an amount; otherwise the saved budget is used |
| no time period | `--week`, and say that's what you looked at |

## 2. Run it as JSON

```
python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --json --sessions 3 FLAGS
```

- Without `--daily` you get `total_cost`, `total_tokens`, `budget` (or null) and `projects`, most expensive first.
  Each project has `cost`, `tips` and `sessions`. Each session has `start`, `model`, `turns`, `cost`,
  `cost_as_cheaper`, `spent` (`read` re-reading history, `write` saving history, `out` Claude's writing,
  `in` new input), `peak_context`, `cold_restarts` and `tips`.
- With `--daily` you get `days` (`date`, `cost`) and `total_cost`.

## 3. Answer

- Lead with the direct answer and the number, e.g. "About $14 this week, most of it in myapp."
- For "why": name the biggest part of `spent` and the top tip, in everyday words. Re-reading history means
  the chat got long. A cold restart means it resumed after a long break.
- For "how to save": give at most three tips, biggest saving first, from the `tips` fields. Don't invent advice.
- Keep it to 2–5 sentences, with a short list only if it really helps.
- Costs are estimates at API list prices. On a Pro/Max plan, say it reflects how fast they use their limit,
  not a bill.
- If nothing is found, say so and suggest a wider range (`--week` → `--since` a month ago).
- This only covers Claude Code, not claude.ai chats. Say so if they ask about the web or the Chat tab.
- If they want to see it rather than read it, offer `/tokenwatch:dashboard`.
