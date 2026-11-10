---
description: Turn on the tokenwatch live statusline in your Claude Code settings
allowed-tools: Read, Edit, Write
---

Enable the tokenwatch statusline by setting `statusLine` in `~/.claude/settings.json`
to exactly this (copy it character for character; it contains no version or install path,
because it finds the newest installed tokenwatch each time it runs):

```json
{"type": "command", "command": "python3 -I -c \"import glob,os,runpy,sys;r=os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude');v=lambda p:[int(x) if x.isdigit() else -1 for x in os.path.basename(os.path.dirname(p)).split('.')];s=max(glob.glob(os.path.join(r,'plugins','cache','tokenwatch','tokenwatch','*','statusline.py')),key=v,default='');s or sys.exit();sys.path.insert(0,os.path.dirname(s));sys.argv=[s];runpy.run_path(s,run_name='__main__')\"", "refreshInterval": 2}
```

Create the file if missing and keep every other setting untouched. If a different
`statusLine` already exists, tell me what it was before replacing it.

After saving, run `python3 "${CLAUDE_PLUGIN_ROOT}/twlib/install.py" --verify` with Bash. If it
reports a mismatch, fix the value it prints and run it again until it says the statusline is set up.

Then look at `hooks.SessionStart` in the same file. If a command there runs a `sessionstart.py`
from a tokenwatch folder outside `~/.claude/plugins` (an old manual install), tell me it duplicates
the plugin's own greeting and offer to remove just that entry. Don't remove it unless I say yes.

Finally say the statusline appears on the next refresh and keeps working after plugin updates,
so setup doesn't need to be run again.
