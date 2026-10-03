# tokenwatch

See where your Claude Code tokens actually go — and get told what to fix.

tokenwatch reads the transcripts Claude Code already keeps on your machine
(`~/.claude/projects/`) and turns them into plain advice:

- *"this plugin injected itself 13× into a project that never uses it — disable it"*
- *"120-turn marathon session — `/clear` between phases would have cut re-reading"*
- *"you ran `gh` 40× in Bash — a GitHub MCP server would be cheaper"*
- *"these connected MCP servers were never called here — pure context overhead"*

**Everything is local.** No network calls, no telemetry, nothing leaves your
machine. It's a few hundred lines of dependency-free Python you can read in
one sitting.

## The three surfaces

### 1. CLI report

```
python3 tokenwatch.py              # all projects, ranked by weighted cost
python3 tokenwatch.py --project myapp
```

```
━━ ~/Desktop/myapp
   1 session(s) · 120 turns · out 90K · in 10K · cache w 1M / r 8M · weighted ≈ 3M input-equivalent tokens
   ⚠ some-plugin: injected itself ~13x into this project's sessions. If this project
     doesn't use it, disable it (/plugins) — it rides along in every cache write.
   ◦ marathon session (120 turns, 8M cache reads): /clear between unrelated phases
     would have cut re-reading.
```

"Weighted" converts the four token kinds (input, output, cache write, cache
read) into input-equivalent units using typical relative prices, so a number
dominated by cheap cache reads doesn't look scarier than it is.

### 2. Statusline — live burn meter inside Claude Code

```
🪙 ≈3M eq · ↑90K out · 120t · ⚠ plugin bloat (/plugins)
```

Add to `~/.claude/settings.json` (replace the path with wherever you cloned this):

```json
{
  "statusLine": {
    "type": "command",
    "command": "python3 /path/to/tokenwatch/statusline.py",
    "refreshInterval": 15
  }
}
```

It tails the transcript incrementally (state cached in `/tmp`), so a refresh
costs ~60 ms even on huge sessions.

### 3. Session greeting — one line when a session starts

```
tokenwatch: last session ≈3M eq tokens, 90K out, 120 turns. ⚠ plugin bloat: /plugins.
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

One short line on purpose — advice about token waste shouldn't waste tokens.

## Requirements

- Claude Code with local transcripts (the default)
- Python 3.9+ (no packages needed)

## License

MIT
