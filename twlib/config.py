"""Where Claude Code keeps its transcripts, and where tokenwatch may write its own files."""
import os, tempfile

HOME = os.path.expanduser("~")

PROJECTS = os.path.join(HOME, ".claude", "projects")

# Only ever read (by the greeting's "re-run setup" reminder); tokenwatch never writes it.
SETTINGS = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude"), "settings.json")

# Saved settings (budget, theme). Outside ~/.claude on purpose: tokenwatch never writes there.
PREFS = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "tokenwatch", "config.json")

# Small bookkeeping (e.g. which week's recap was shown). Never settings, never transcripts.
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.join(HOME, ".local", "state"), "tokenwatch", "recap.json")

# --open writes the dashboard here: a per-user folder in the system temp dir, never inside ~/.claude.
OUT_DIR = os.path.join(tempfile.gettempdir(), "tokenwatch-%s" % getattr(os, "getuid", lambda: "user")())


def private_dir():
    """OUT_DIR, created readable only by you. Raises OSError for a symlink or a folder someone else owns."""
    d = OUT_DIR
    os.makedirs(d, mode=0o700, exist_ok=True)
    st = os.lstat(d)
    if os.path.islink(d) or (hasattr(os, "getuid") and st.st_uid != os.getuid()):
        raise PermissionError(f"{d} is not a folder you own")
    os.chmod(d, 0o700)
    return d
