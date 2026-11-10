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
| `tokenwatch.py` | Thin entry point and compatibility shim. Re-exports every `twlib` name so `from tokenwatch import ...` keeps working. |
| `twlib/fmt.py` | `fmt`, `money`, `nice`, `when` formatting helpers. |
| `twlib/pricing.py` | `KINDS`, `PRICES`, `cost_parts`, `cost_of`. Update `PRICES` when prices change. |
| `twlib/usage.py` | `new_usage`, `context_of`, `plugin_hook`: reading one transcript line. |
| `twlib/tips.py` | `top_tip`, `session_tips`, `advise`: the plain-English suggestions. |
| `twlib/live.py` | Live-session state shared by `statusline.py` and `pet.py`. |
| `twlib/config.py` | `HOME`, `PROJECTS`. Read as `config.PROJECTS` so tests can redirect it. |
| `twlib/dates.py` | `session_date`, `date_range`, `period_range`. |
| `twlib/scan.py` | `scan_session`, `scan_project`, `project_name`: transcripts to numbers. |
| `twlib/budget.py` | Budget parsing, status and the printed line. |
| `twlib/trend.py` | Daily totals, sparkline, trend table. |
| `twlib/report.py` | JSON-serialisable session/project summaries. |
| `examples/demo.py` | Builds FAKE transcripts and renders the README examples with the real CLI. `--update-readme` rewrites the `<!-- demo:NAME -->` blocks, `--dashboard` rewrites `examples/dashboard-sample.html`, `--check` (run in the tests) verifies both. |
| `docs/dashboard.png` | Screenshot of `examples/dashboard-sample.html` (made-up data only), shown in the README. Retake it after visible changes to `twlib/dashboard.py`; check it shows no real names, tabs or paths before committing. |
| `examples/dashboard-sample.html` | Generated sample dashboard from fake data. Never edit by hand and never commit a dashboard made from real transcripts. |
| `twlib/cli.py` | Argument parsing and report printing (`main`). |
| `twlib/dashboard.py` | `--export html`: `collect()` (data dict) and `render_html()` (inline CSS/SVG page, tooltip-only script). Escape every data string with `esc()`. |
| `statusline.py` | Claude Code statusline. Tails the transcript incrementally; state cached in `/tmp/tokenwatch-*.json`. |
| `sessionstart.py` | SessionStart hook: one line about the previous session. |
| `pet.py` | Long-running animated cat for a second terminal. |
| `commands/*.md` | Plugin slash commands (`report`, `setup`, `pet`). |
| `hooks/hooks.json` | Registers the SessionStart hook for plugin installs. |
| `.claude-plugin/` | Plugin and marketplace manifests. Bump `version` in `plugin.json` on user-visible changes. |

## Things to know

- **Every CLI option must be registered in `twlib/cli.py` (`FLAGS`).** Unknown options exit with status 2 and a
  did-you-mean hint instead of being ignored. Add new flags to `FLAGS` (and `--help`) or they will be rejected.
  `pet.py` has its own options and does not use this check.

- Claude Code writes one transcript line per content block and repeats the reply's `usage` on each,
  so replies are counted once by message id (`new_usage`).
- Costs are estimates at public list prices (`PRICES`, matched by prefix, most specific first).
  Unknown models cost 0. Update `PRICES` when prices change.
- Cache writes are 1.25x input price (5-minute cache) or 2x (1-hour cache).
- `statusline.py`, `pet.py` and `sessionstart.py` import from `tokenwatch`/`twlib`, so keep imports free of side
  effects (`main()` only runs under `__main__`). Tests redirect transcripts with `twlib.config.PROJECTS`, never the real folder. `twlib` modules must not import `tokenwatch` (no cycles).

## Running

```
python3 tokenwatch.py [--project NAME] [--sessions N]
python3 statusline.py < statusline-input.json
python3 pet.py --demo
python3 -m unittest discover -s tests -v   # run all tests
python3 -m unittest tests.test_budget      # run one module's tests
```

## Tests

One file per `twlib` module in `tests/` (`test_scan.py`, `test_budget.py`, ...). Shared helpers live in
`tests/helpers.py`: `reply`/`write_session` build synthetic transcripts, and the `CliRunner` mixin runs the
CLI against a temp folder. Tests must never read real transcripts: always go through `helpers`.

## README examples

Never hand-write output samples in the README. The `session`, `report`, `daily` and `budget` blocks are generated
from invented data: after changing output formats, run `python3 examples/demo.py --update-readme` and commit the
result (`tests/test_examples.py` fails otherwise). Never paste real transcripts or real output into docs. The sample dashboard is generated the same way
(`python3 examples/demo.py --dashboard`); regenerate it after any change to `twlib/dashboard.py`.

## Commits and PRs

One small, focused commit per logical change. One PR per goal. Keep the README in sync with any
new flag or behaviour.
