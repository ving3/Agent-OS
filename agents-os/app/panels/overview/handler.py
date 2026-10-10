# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Overview (Dashboard principal)
Affiche la grille des agents, leurs statistiques et profils.
"""
import time

from config import AGENTS, PANELS
from database import check_agent_access
from hermes_client import (
    get_agent_memory, list_profiles, list_skills,
    stats, stats_lock
)


def handle_status(handler, user):
    """GET /api/status — Statistiques generales du dashboard."""
    with stats_lock:
        uptime = time.time() - stats["start_time"]
        handler._send_json({
            "status": "online", "uptime_seconds": int(uptime),
            "total_calls": stats["total_calls"],
            "calls_per_agent": stats["calls_per_agent"],
            "errors": stats["errors"],
            "profiles": list_profiles(),
            "agents": AGENTS,
            "panels": PANELS,
            "user": {"name": user["name"], "email": user["email"], "role": user["role"],
                     "permissions": user.get("permissions", {})},
        })


def handle_profiles(handler, user):
    """GET /api/profiles — Liste des profils agents avec leur memoire."""
    profiles = []
    for name in list_profiles():
        if not check_agent_access(user, name):
            continue
        mem = get_agent_memory(name)
        ai = AGENTS.get(name, {})
        profiles.append({
            "name": name, "emoji": ai.get("emoji", "\U0001F916"),
            "color": ai.get("color", "#58a6ff"),
            "description": ai.get("desc", ""), "memory": mem, "has_memory": bool(mem),
        })
    handler._send_json({"profiles": profiles})


def handle_profile(handler, pname):
    """GET /api/profile/<name> — Profil d'un agent specifique."""
    mem = get_agent_memory(pname)
    ai = AGENTS.get(pname, {})
    handler._send_json({"name": pname, "emoji": ai.get("emoji", "\U0001F916"),
                        "description": ai.get("desc", ""), "memory": mem})


def handle_models(handler):
    """GET /v1/models — Liste des modeles OpenAI-compatible disponibles."""
    models = [{"id": f"hermes-{k}", "object": "model", "created": int(time.time()), "owned_by": "hermes"}
              for k in AGENTS]
    handler._send_json({"object": "list", "data": models})
