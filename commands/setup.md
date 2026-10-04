---
description: Turn on the tokenwatch live statusline in your Claude Code settings
allowed-tools: Read, Edit, Write
---

Enable the tokenwatch statusline by setting `statusLine` in `~/.claude/settings.json`
to exactly:

```json
{ "type": "command", "command": "python3 \"${CLAUDE_PLUGIN_ROOT}/statusline.py\"", "refreshInterval": 2 }
```

Resolve `${CLAUDE_PLUGIN_ROOT}` to its absolute path first (this plugin's install
directory is `${CLAUDE_PLUGIN_ROOT}`), because settings.json does not expand it.
Create the file if missing, keep every other setting untouched, and if a different
`statusLine` already exists, tell me what it was before replacing it. Then say the
statusline appears on the next refresh, and that `/tokenwatch:setup` should be re-run
after a plugin update since the install path can change.
