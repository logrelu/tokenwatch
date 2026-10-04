---
description: Show how to run the animated tokenwatch cat (Purr) in a second terminal
allowed-tools: Bash(echo:*)
---

The live pet is a long-running animation, so it can't run inside this chat. Tell me to open a
second terminal pane or tab and run this shell command there (Ctrl-C stops it):

```
python3 "${CLAUDE_PLUGIN_ROOT}/pet.py"
```

Resolve `${CLAUDE_PLUGIN_ROOT}` to this plugin's absolute install path before printing it, so I can
paste it as-is. Mention the options: `--project NAME` to follow one project, `--fps N` to change the
frame rate (default 8), and `--demo` to preview all five moods without a session. Do not try to run
it yourself.
