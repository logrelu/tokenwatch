"""Scanning transcripts into per-session and per-project numbers."""
import glob, json, os
from collections import defaultdict
from twlib.config import HOME
from twlib.dates import session_date
from twlib.pricing import KINDS, CHEAPER, cost_parts, cost_of
from twlib.usage import new_usage, context_of, plugin_hook
from twlib.tips import session_tips

def scan_session(f):
    """Everything tokenwatch knows about one session transcript."""
    s = dict(file=f, start="", turns=0, cost=0.0, tokens={k: 0 for k in KINDS},
             spent={"read": 0.0, "write": 0.0, "out": 0.0, "in": 0.0}, as_cheaper=0.0,
             peak=0, context=0, first_write=0, model="", rebuilds=0, rebuild_cost=0.0,
             hook_runs=0, hook_secs=0.0, hook_chars=0, plugins=set(), bash=[], mcp=defaultdict(int),
             daily=defaultdict(float))
    seen = []
    with open(f, errors="ignore") as fh:
        lines = fh.readlines()
    for line in lines:
        h = plugin_hook(line)
        if h:
            s["hook_runs"] += h[0]; s["hook_secs"] += h[1]; s["hook_chars"] += h[2]; s["plugins"].update(h[3])
            continue
        try: d = json.loads(line)
        except Exception: continue
        if not s["start"]: s["start"] = d.get("timestamp") or ""
        msg = d.get("message") or {}
        u = new_usage(msg, seen)
        if u:
            model = msg.get("model") or ""
            parts = cost_parts(model, u)
            s["turns"] += 1
            s["cost"] += sum(parts.values())
            s["as_cheaper"] += cost_of(CHEAPER, u)
            for k in parts: s["spent"][k] += parts[k]
            day = session_date(d.get("timestamp") or "")
            if day: s["daily"][day] += sum(parts.values())
            for k in KINDS: s["tokens"][k] += u.get(k, 0)
            if model.startswith("claude"): s["model"] = model
            s["context"] = context_of(u); s["peak"] = max(s["peak"], s["context"])
            w = u.get("cache_creation_input_tokens", 0)
            if s["turns"] == 1:
                s["first_write"] = w
            elif w > 50_000 and w > 0.5 * s["context"]:
                # most of the conversation written to cache again: the saved copy had expired
                s["rebuilds"] += 1; s["rebuild_cost"] += parts["write"]
        for c in (msg.get("content") or []) if isinstance(msg.get("content"), list) else []:
            if isinstance(c, dict) and c.get("type") == "tool_use":
                name = c.get("name", "")
                if name.startswith("mcp__"):
                    s["mcp"][name.split("__")[1]] += 1
                elif name == "Bash":
                    s["bash"].append((c.get("input") or {}).get("command", "")[:200])
    return s

def scan_project(pdir, since=None, until=None):
    sessions = [scan_session(f) for f in sorted(glob.glob(os.path.join(pdir, "*.jsonl")))]
    if since or until:
        def inside(x):
            d = session_date(x["start"])
            return d is not None and (not since or d >= since) and (not until or d <= until)
        sessions = [x for x in sessions if inside(x)]
    stats = {k: sum(s["tokens"][k] for s in sessions) for k in KINDS}
    mcp = defaultdict(int)
    for s in sessions:
        for k, v in s["mcp"].items(): mcp[k] += v
    return dict(sessions=sessions, stats=stats, cost=sum(s["cost"] for s in sessions),
                turns=sum(s["turns"] for s in sessions), mcp=mcp,
                bash=[c for s in sessions for c in s["bash"]])

def project_name(pdir):
    return os.path.basename(pdir).replace("-Users-" + os.path.basename(HOME) + "-", "~/").replace("-", "/")
