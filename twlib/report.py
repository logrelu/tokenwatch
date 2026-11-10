"""JSON-serialisable summaries of sessions and projects (--json)."""
import os
from twlib.tips import session_tips, advise

def session_summary(s):
    """One session as plain JSON-serialisable data (used by --json)."""
    return {"id": os.path.splitext(os.path.basename(s["file"]))[0], "start": s["start"], "model": s["model"],
            "turns": s["turns"], "cost": round(s["cost"], 4), "cost_as_cheaper": round(s["as_cheaper"], 4),
            "tokens": dict(s["tokens"]), "spent": {k: round(v, 4) for k, v in s["spent"].items()},
            "peak_context": s["peak"], "cold_restarts": s["rebuilds"], "hook_runs": s["hook_runs"],
            "agents": s.get("agents", 0), "agent_turns": s.get("agent_turns", 0),
            "agent_cost": round(s.get("agent_cost", 0.0), 4),
            "tips": session_tips(s)}

def project_summary(name, p, show):
    done = sorted((x for x in p["sessions"] if x["turns"]), key=lambda x: x["start"], reverse=True)
    return {"project": name, "cost": round(p["cost"], 4), "turns": p["turns"], "tokens": dict(p["stats"]),
            "sessions_total": len(done), "tips": advise(p), "mcp_used": dict(p["mcp"]),
            "sessions": [session_summary(x) for x in done[:show]]}
