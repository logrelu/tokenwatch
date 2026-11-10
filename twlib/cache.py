"""Per-file scan cache: remembers scan_session() results so unchanged transcripts aren't read again.

One JSON file, config.CACHE (None disables it). An entry is used only when the size and mtime of the
session's transcript and every subagent transcript match what was scanned, and the whole file is discarded
when VERSION or the price table changes. Nothing here raises: a broken cache only means a full scan.
"""
import atexit, hashlib, json, os, tempfile
from collections import defaultdict
from datetime import date
from twlib import config
from twlib.pricing import CHEAPER, KINDS, PRICES

VERSION = 1     # bump whenever scan_session's output changes, so old entries aren't reused

def make_stamp(prices=PRICES, cheaper=CHEAPER, kinds=KINDS, version=VERSION):
    """Identifies the code and prices a cache was built with; any change means a full rescan."""
    return "%d-%s" % (version, hashlib.sha1(repr((prices, cheaper, kinds)).encode()).hexdigest()[:12])

STAMP = make_stamp()

_mem = {"path": None, "entries": {}, "dirty": False, "hooked": False}


def signature(files):
    """[[path, size, mtime_ns], ...] for `files`; None if any is gone."""
    try:
        return [[f, st.st_size, st.st_mtime_ns] for f, st in ((f, os.stat(f)) for f in files)]
    except OSError:
        return None


def _entries():
    """The loaded cache entries for config.CACHE ({} when disabled, missing, stale or unreadable)."""
    path = config.CACHE
    if _mem["path"] != path:
        _mem.update(path=path, entries={}, dirty=False)
        if path:
            try:
                with open(path, encoding="utf-8") as fh: d = json.load(fh)
                if isinstance(d, dict) and d.get("stamp") == STAMP and isinstance(d.get("entries"), dict):
                    _mem["entries"] = d["entries"]
            except (OSError, ValueError): pass
    return _mem["entries"]


def encode(s):
    """A scan_session() dict as JSON-safe data, sharing nothing with `s` (callers may change their copy)."""
    out = dict(s)
    out["plugins"] = sorted(s["plugins"])
    out["mcp"] = dict(s["mcp"])
    out["daily"] = {d.isoformat(): v for d, v in s["daily"].items()}
    return json.loads(json.dumps(out))


def decode(d):
    """The inverse of encode(): sets, defaultdicts and date keys back."""
    s = dict(d)
    s["plugins"] = set(d["plugins"])
    s["mcp"] = defaultdict(int, d["mcp"])
    s["daily"] = defaultdict(float, {date.fromisoformat(k): v for k, v in d["daily"].items()})
    s["tokens"], s["spent"], s["bash"] = dict(d["tokens"]), dict(d["spent"]), list(d["bash"])
    return s


def get(f, sig):
    """The cached session for transcript `f` if `sig` (signature of it and its subagents) still matches."""
    if not sig or not config.CACHE: return None
    e = _entries().get(f)
    try:
        return decode(e["s"]) if e and e.get("sig") == sig else None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None


def put(f, sig, s):
    """Remember session `s` for transcript `f`; written to disk when the process exits (or by save())."""
    if not sig or not config.CACHE: return
    _entries()[f] = {"sig": sig, "s": encode(s)}
    _mem["dirty"] = True
    if not _mem["hooked"]:
        atexit.register(save)
        _mem["hooked"] = True


def save():
    """Write the cache if anything changed, dropping entries for transcripts that no longer exist.
    Folder 0700, file 0600, replaced atomically. Never raises."""
    path = _mem["path"]
    if not (_mem["dirty"] and path and path == config.CACHE): return
    try:
        folder = config.private_dir(os.path.dirname(path))
        entries = {f: e for f, e in _mem["entries"].items() if os.path.exists(f)}
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".scan-", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump({"stamp": STAMP, "entries": entries}, fh, separators=(",", ":"))
            os.chmod(tmp, 0o600)
            os.replace(tmp, path)
        except BaseException:
            try: os.unlink(tmp)
            except OSError: pass
            raise
        _mem.update(entries=entries, dirty=False)
    except Exception:
        pass


def reset():
    """Forget what's loaded in memory (tests; the next lookup reads config.CACHE again)."""
    _mem.update(path=None, entries={}, dirty=False)
