"""Reading one transcript line: reply usage, context size and plugin-hook records."""
import json, re

def new_usage(msg, seen):
    """The usage of a reply not counted yet, else None. Claude Code writes one transcript line
    per content block and repeats the reply's usage on each, so every reply is counted once by id.
    A reply's lines sit together, so `seen` only needs to remember recent ids."""
    u, mid = msg.get("usage"), msg.get("id")
    if not u or (mid and mid in seen): return None
    if mid:
        seen.append(mid)
        if len(seen) > 100: del seen[:-50]
    return u

def context_of(u):
    """How many tokens of conversation the model had to read for this reply."""
    return u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0) + u.get("cache_read_input_tokens", 0)

PLUGIN_MARK = re.compile(r"\[([\w-]+-plugin)\]")

def plugin_hook(line):
    """(runs, seconds, characters added to the chat, plugin names) if this transcript line records
    a plugin hook, else None. Only real hook records count, so a chat that merely talks about a
    plugin doesn't look like bloat. `content` is what reached the model (big output is truncated)."""
    if '"attachment"' not in line or ("CLAUDE_PLUGIN_ROOT" not in line and '"hook_additional_context"' not in line):
        return None
    try: a = json.loads(line).get("attachment") or {}
    except Exception: return None
    kind, content = a.get("type") or "", a.get("content") or ""
    if not isinstance(content, str): content = "\n".join(map(str, content))
    names = PLUGIN_MARK.findall(content)
    if kind == "hook_additional_context":
        return (0, 0.0, len(content), names) if names else None
    if kind.startswith("hook_") and "CLAUDE_PLUGIN_ROOT" in (a.get("command") or ""):
        try: secs = float(a.get("durationMs") or 0) / 1000
        except ValueError: secs = 0.0
        return (1, secs, len(content), names)
    return None
