# -*- coding: utf-8 -*-
"""Agent OS — Router Dashboard (status, profils, skills, modèles)"""
import time
from fastapi import APIRouter, Request
from database import get_user_from_token, check_agent_access
from services.hermes_client import (
    stats, stats_lock, get_agent_memory, list_skills, list_profiles,
)
from config import AGENTS, PANELS
from schemas import (
    SystemStatus, ProfileListResponse, ProfileResponse,
    SkillListResponse, ModelListResponse, ModelInfo, ErrorResponse,
    UserInfo, UserPermissions, AgentConfig,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


def _get_user(request: Request) -> dict | None:
    token = request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    return get_user_from_token(token)


def _require_auth(request: Request) -> dict | None:
    return _get_user(request)


@router.get("/status", response_model=SystemStatus | ErrorResponse)
def get_status(request: Request):
    user = _require_auth(request)
    if not user:
        return {"error": "Non autorisé"}
    with stats_lock:
        uptime = int(time.time() - stats["start_time"])
        return {
            "status": "online",
            "uptime_seconds": uptime,
            "total_calls": stats["total_calls"],
            "calls_per_agent": dict(stats["calls_per_agent"]),
            "errors": stats["errors"],
            "profiles": list_profiles(),
            "agents": {k: AgentConfig(emoji=v["emoji"], color=v["color"], desc=v["desc"]).model_dump()
                       for k, v in AGENTS.items()},
            "panels": PANELS,
            "user": {"id": user["id"], "name": user["name"], "email": user["email"],
                     "role": user["role"], "permissions": user.get("permissions", {})},
        }


@router.get("/profiles", response_model=ProfileListResponse)
def get_profiles(request: Request):
    user = _require_auth(request)
    if not user:
        return {"profiles": []}
    profiles = []
    for name in list_profiles():
        if not check_agent_access(user, name):
            continue
        mem = get_agent_memory(name)
        ai = AGENTS.get(name, {})
        profiles.append({
            "name": name, "emoji": ai.get("emoji", "🤖"),
            "color": ai.get("color", "#58a6ff"),
            "description": ai.get("desc", ""),
            "memory": mem, "has_memory": bool(mem),
        })
    return {"profiles": profiles}


@router.get("/profile/{name}", response_model=ProfileResponse)
def get_profile(name: str, request: Request):
    _require_auth(request)
    mem = get_agent_memory(name)
    ai = AGENTS.get(name, {})
    return {
        "name": name, "emoji": ai.get("emoji", "🤖"),
        "description": ai.get("desc", ""), "memory": mem,
    }


@router.get("/skills", response_model=SkillListResponse)
def get_skills(request: Request):
    _require_auth(request)
    return {"skills": list_skills()}


@router.get("/v1/models", response_model=ModelListResponse)
def get_models(request: Request):
    _require_auth(request)
    now = int(time.time())
    return {"object": "list", "data": [
        ModelInfo(id=f"hermes-{k}", created=now).model_dump() for k in AGENTS
    ]}
