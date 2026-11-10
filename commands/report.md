---
description: Full tokenwatch report (cost, tokens burnt, suggestions) for all projects or one
argument-hint: "[--project NAME] [--week | --today | --since YYYY-MM-DD] [--daily] [--budget N --period day|week|month] [--json] [--export html PATH]"
allowed-tools: Bash(python3:*)
---

Run this and show the output exactly as printed, without summarizing or adding commentary:

!`python3 "${CLAUDE_PLUGIN_ROOT}/tokenwatch.py" $ARGUMENTS`
