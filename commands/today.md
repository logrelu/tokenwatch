---
description: tokenwatch for today: cost, tokens burnt and the top suggestions
argument-hint: "[--project NAME] [--sessions N]"
allowed-tools: Bash(python3:*)
---

Run this and show the output exactly as printed, without summarizing or adding commentary:

!`python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --today --sessions 3 $ARGUMENTS`

If no output appears above (some apps, such as Claude Desktop, don't run that line), run
`python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --today --sessions 3 $ARGUMENTS` with Bash yourself and show its
output exactly as printed. Do not look for the script anywhere else.
