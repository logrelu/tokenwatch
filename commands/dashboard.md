---
description: Open the tokenwatch dashboard in your browser (cost per day, per project, top sessions, tips)
argument-hint: "[--week | --today | --since YYYY-MM-DD] [--project NAME] [--budget N --period day|week|month] [--theme classic|weather]"
allowed-tools: Bash(python3:*)
---

Run this and show the output exactly as printed, without summarizing or adding commentary:

!`python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --open $ARGUMENTS`

If no output appears above (some apps, such as Claude Desktop, don't run that line), run
`python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" --open $ARGUMENTS` with Bash yourself and show its output
exactly as printed. Do not look for the script anywhere else.
