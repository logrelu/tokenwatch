# CLAUDE.md

tokenwatch reads the Claude Code transcripts in `~/.claude/projects/<project>/<session>.jsonl`
and reports cost, tokens burnt and plain-English suggestions. See README.md for user-facing docs.

## Hard rules

- **Local only.** No network calls, no telemetry. Never add one without an explicit opt-in flag.
- **Read-only on transcripts.** Never write to `~/.claude/`.
- **No dependencies.** Python 3.9+ standard library only.
- **Output stays short and plain.** Advice about token waste must not waste tokens
  (the SessionStart hook prints one line on purpose).

## Layout

| File | Role |
|---|---|
| `tokenwatch.py` | Core: `PRICES`, `scan_session`, `session_tips`, `scan_project`, `advise`, CLI `main()`. The other scripts import from here. |
| `statusline.py` | Claude Code statusline. Tails the transcript incrementally; state cached in `/tmp/tokenwatch-*.json`. |
| `sessionstart.py` | SessionStart hook: one line about the previous session. |
| `pet.py` | Long-running animated cat for a second terminal. |
| `commands/*.md` | Plugin slash commands (`report`, `setup`, `pet`). |
| `hooks/hooks.json` | Registers the SessionStart hook for plugin installs. |
| `.claude-plugin/` | Plugin and marketplace manifests. Bump `version` in `plugin.json` on user-visible changes. |

## Things to know

- Claude Code writes one transcript line per content block and repeats the reply's `usage` on each,
  so replies are counted once by message id (`new_usage`).
- Costs are estimates at public list prices (`PRICES`, matched by prefix, most specific first).
  Unknown models cost 0. Update `PRICES` when prices change.
- Cache writes are 1.25x input price (5-minute cache) or 2x (1-hour cache).
- `statusline.py` and `pet.py` import `tokenwatch`, so keep its import free of side effects
  (`main()` only runs under `__main__`).

## Running

```
python3 tokenwatch.py [--project NAME] [--sessions N]
python3 statusline.py < statusline-input.json
python3 pet.py --demo
```

## Commits and PRs

One small, focused commit per logical change. One PR per goal. Keep the README in sync with any
new flag or behaviour.
