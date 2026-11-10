"""The statusline command /tokenwatch:setup writes, and a check for one pinned to an old plugin version.

Claude Code installs each plugin version in its own folder (.../tokenwatch/tokenwatch/<version>/), so a
statusline pointing at one version breaks once that folder is cleaned up after an update. STATUSLINE_COMMAND
contains no version: at run time it picks the newest installed version (compared as numbers, so 0.10.0 beats
0.9.0) and runs its statusline.py. `-I` keeps Python from importing modules from the project you are in.
"""
import json, os, re

_FIND = ("import glob,os,runpy,sys;"
         "r=os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude');"
         "v=lambda p:[int(x) if x.isdigit() else -1 for x in os.path.basename(os.path.dirname(p)).split('.')];"
         "s=max(glob.glob(os.path.join(r,'plugins','cache','tokenwatch','tokenwatch','*','statusline.py')),key=v,default='');"
         "s or sys.exit();"
         "sys.path.insert(0,os.path.dirname(s));sys.argv=[s];runpy.run_path(s,run_name='__main__')")

STATUSLINE_COMMAND = 'python3 -I -c "%s"' % _FIND

STATUSLINE = {"type": "command", "command": STATUSLINE_COMMAND, "refreshInterval": 2}

_PINNED = re.compile(r"plugins[/\\]cache[/\\]tokenwatch[/\\]tokenwatch[/\\]([^/\\\"']+)[/\\]statusline\.py")


def pinned_version(settings):
    """The plugin version a settings dict's statusline is pinned to, or None (not pinned, or not tokenwatch)."""
    cmd = ((settings or {}).get("statusLine") or {}).get("command") or ""
    m = _PINNED.search(cmd)
    return m.group(1) if m and "*" not in m.group(1) else None


def read_settings(path):
    """settings.json as a dict; {} if it is missing or unreadable. Read-only."""
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def verify(path):
    """One line saying whether settings.json at `path` has exactly STATUSLINE; True when it does."""
    got = read_settings(path).get("statusLine")
    if got == STATUSLINE:
        print("tokenwatch: statusline is set up and will follow plugin updates")
        return True
    print("tokenwatch: statusLine in %s does not match; set it to exactly:\n%s" % (path, json.dumps(STATUSLINE)))
    return False


if __name__ == "__main__":      # python3 twlib/install.py --verify [SETTINGS_PATH]; read-only
    import sys
    rest = [a for a in sys.argv[1:] if a != "--verify"]
    default = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"), "settings.json")
    sys.exit(0 if verify(rest[0] if rest else default) else 1)
