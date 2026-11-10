"""Where Claude Code keeps its transcripts, and where tokenwatch may write its own files."""
import os, tempfile

HOME = os.path.expanduser("~")

PROJECTS = os.path.join(HOME, ".claude", "projects")

# Only ever read (by the greeting's "re-run setup" reminder); tokenwatch never writes it.
SETTINGS = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(HOME, ".claude"), "settings.json")

# Saved settings (budget, theme). Outside ~/.claude on purpose: tokenwatch never writes there.
PREFS = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.join(HOME, ".config"), "tokenwatch", "config.json")

# --open writes the dashboard here: a per-user folder in the system temp dir, never inside ~/.claude.
OUT_DIR = os.path.join(tempfile.gettempdir(), "tokenwatch-%s" % getattr(os, "getuid", lambda: "user")())
