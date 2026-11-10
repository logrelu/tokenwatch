"""Where Claude Code keeps its transcripts, and where tokenwatch may write its own files."""
import os, tempfile

HOME = os.path.expanduser("~")

PROJECTS = os.path.join(HOME, ".claude", "projects")

# --open writes the dashboard here: a per-user folder in the system temp dir, never inside ~/.claude.
OUT_DIR = os.path.join(tempfile.gettempdir(), "tokenwatch-%s" % getattr(os, "getuid", lambda: "user")())
