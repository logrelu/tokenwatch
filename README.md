# tokenwatch

```
    /\_/\
   ( o.o )   purr-fect token watch
    > ^ <

   ┌─────────┐
   │ ◉     ◉ │   tick tock, token watch
   │   ───   │
   └──┬───┬──┘
  ╭───┴───┴───╮
  │  🪙 $$$   │
  ╰───────────╯
```

See where your Claude Code tokens actually go — and get told what to fix.

tokenwatch reads the transcripts Claude Code already keeps on your machine
(`~/.claude/projects/`) and turns them into a cost, a token count and plain advice.

## Example

One real session, as the report shows it:

```
▸ 1 Oct 10:00 · 🪙 ≈$12 · 🔥 8M tokens · 120 turns · Opus 5.5
  where it went: re-reading history $7.20 · saving history $3.90 · Claude's writing $1.10 · new input $0.05
  💡 long chat: 60% of the cost ($7.20) was Claude re-reading the conversation, up to 210K tokens on every step. /clear when you switch tasks, /compact inside a long one.
  💡 cold restarts: 5 times the whole conversation had to be saved again (≈$3.10), usually after a break of an hour or more. After a long break, /clear and start fresh rather than continuing a huge chat.
  💡 plugin hooks (some-plugin) ran 400 times, ≈7 min of hook time, and added ≈1K tokens to the chat. If this project doesn't use that plugin, turn it off in /plugins.
  💡 model: this ran on Opus 5.5. The same tokens at Sonnet 5.5 prices come to ≈$2.40: /model sonnet for routine work.
```

What it is telling you:

- **Line 1** — when the session started, what it cost, how many tokens it used, how
  many steps Claude took, and which model did the work.
- **Where it went** — the cost split four ways. *Re-reading history* is Claude reading
  the whole conversation again on every step. *Saving history* is storing new
  material (your messages, files Claude opened, its own replies) so later steps can
  re-read it cheaply. *Claude's writing* is the replies and code. *New input* is the
  small remainder that is read once without being saved.
- **💡 lines** — every suggestion that applies, biggest saving first, each with the
  number behind it. Here: the chat was too long, it was resumed after long breaks five
  times, a plugin ran on nearly every action, and a cheaper model would have cost a fifth.

## How to read it (no dev knowledge needed)

Everything tokenwatch prints is built from the same three parts:

- 🪙 **cost** — what the session would cost at public API prices. On a Pro/Max
  subscription you aren't billed this; read it as how fast you're using up your limit.
- 🔥 **tokens burnt** — how much text Claude read and wrote. Most of it is Claude
  re-reading the conversation so far on every step, which is why long chats get expensive.
- 💡 **suggestions** — what is most worth doing. The status line shows the top one
  (or a happy 😺 `running lean` (a worried 🙀 comes with the tip)); the report lists every one that applies.

The data is the transcripts Claude Code already saves at
`~/.claude/projects/<project>/<session>.jsonl`. tokenwatch only reads them.

**Everything is local.** No network calls, no telemetry, nothing leaves your
machine. It's a few hundred lines of dependency-free Python you can read in
one sitting.

## Install as a plugin

```
/plugin marketplace add logrelu/tokenwatch
/plugin install tokenwatch@tokenwatch
/tokenwatch:setup      # turns on the live statusline
```

This gives you the session greeting automatically, `/tokenwatch:report [--project NAME]`
for the full report, and `/tokenwatch:setup` for the statusline (plugins can't enable
a statusline on their own, so setup writes it to `~/.claude/settings.json`; re-run it
after a plugin update). The manual setup below still works if you'd rather not use the plugin.

## The three surfaces

### 1. CLI report

```
python3 tokenwatch.py              # all projects, most expensive first
python3 tokenwatch.py --project myapp
```

```
🤖 ━━ ~/Desktop/myapp
   🪙 ≈$14 · 🔥 9M tokens burnt · 2 session(s) · 140 turns
   out 291K · in 32K · cache w 2M / r 8M
   ⚠ heavy session start: ~51K tokens of context are loaded before any work happens. That's tool lists, connectors, plugins and CLAUDE.md. Prune what this project doesn't use.
   ◦ MCP actually used here: some-server (6x). Any other connected server is pure context overhead for this project.

   ▸ 2 Oct 09:30 · 🪙 ≈$2.10 · 🔥 1M tokens · 20 turns · Opus 5.5
     where it went: re-reading history $0.30 · saving history $1.20 · Claude's writing $0.60 · new input $0.00
     💡 model: this ran on Opus 5.5. The same tokens at Sonnet 5.5 prices come to ≈$0.50: /model sonnet for routine work.

   ▸ 1 Oct 10:00 · 🪙 ≈$12 · 🔥 8M tokens · 120 turns · Opus 5.5
     ...the session from the example above...

🤖 ═══ all projects: 🪙 ≈$14 at API list prices · 🔥 9M tokens burnt
```

Projects are listed most expensive first. Each starts with its totals and the
project-wide suggestions, then its 5 most recent sessions (`--sessions 20` for more)
in the format shown in the example.

Cost prices each reply by the model that wrote it and by token kind (input,
output, cache write, cache read), using the list prices in `PRICES` at the top
of `tokenwatch.py`. Update that table when prices change. It is an estimate for
spotting waste, not an invoice.

### 2. Statusline — live burn meter inside Claude Code

```
🤖 ≈$12 · 🔥 8M tokens burnt · 120 turns
        ~(=^.^=)    purring along · $0.04/min
```

Line 2 is Purr, a cat that patrols the line and reacts to how fast you are
spending. First match wins:

- `(=@_@=)$` overheated: context over 200K or a tip is showing (the tip appears on line 1 with 🙀)
- `(=-.-=)zZ` sleepy: no turns yet, or no spend for 5 minutes
- `~(=>.<=)*` on fire: burning $0.50/min or more, runs fast
- `~(=^.^;)` warming up: $0.10/min or more, or context past 100K
- `~(=^.^=)` calm: everything else

Set `"refreshInterval": 2` so the cat animates. It adapts to narrow terminals,
honours `NO_COLOR`, and `TOKENWATCH_COLOR=0` turns its colour off.

Add to `~/.claude/settings.json` (replace the path with wherever you cloned this):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/tokenwatch/statusline.py",
    "refreshInterval": 2
  }
}
```

It tails the transcript incrementally (state cached in `/tmp`), so a refresh
costs ~60 ms even on huge sessions.

### 3. Session greeting — one line when a session starts

```
🤖 tokenwatch: last session cost ≈$12 · 🔥 8M tokens burnt · 120 turns. 💡 long chat: 60% of the cost ($7.20) was Claude re-reading the conversation, up to 210K tokens on every step. /clear when you switch tasks, /compact inside a long one. (+3 more: python3 /path/to/tokenwatch.py)
```

```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command",
          "command": "python3 /path/to/tokenwatch/sessionstart.py 2>/dev/null || true",
          "timeout": 30 } ] }
    ]
  }
}
```

One line on purpose — advice about token waste shouldn't waste tokens. It carries the
top suggestion; the full list is in the CLI report.

### Live pet (second terminal)

The statusline can only refresh about once a second, so Purr can't truly animate there. `pet.py` is a
long-running companion: run it in a second terminal pane or tab and Purr patrols the whole width at ~8 fps,
with the same moods and numbers as the statusline (calm stroll, brisk warming, flaming sprint when it's
burning money, steaming when the context is huge, curled up with floating z's when idle).

```
python3 /path/to/tokenwatch/pet.py [--project NAME] [--fps N]
python3 /path/to/tokenwatch/pet.py --demo      # cycles all five moods, no session needed
```

It follows your newest transcript (and switches when a newer one appears), redraws a 4-line block in
place, and restores your cursor on Ctrl-C. Honours `NO_COLOR` and `TOKENWATCH_COLOR=0`. In a plugin
install, `/tokenwatch:pet` prints the exact command to paste.

## Requirements

- Claude Code with local transcripts (the default)
- Python 3.9+ (no packages needed)

## License

MIT
