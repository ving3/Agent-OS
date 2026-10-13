# -*- coding: utf-8 -*-
"""Agent OS — Router Admin (CRUD utilisateurs, gestion agents)"""
import json
import os
from fastapi import APIRouter, Request, Response
from database import get_db, get_user_from_token, hash_password
from services.hermes_client import list_profiles, create_agent_profile, delete_agent_profile
from config import PANELS, AGENTS, PROVIDERS
from schemas import (
    UserListResponse, CreateUserRequest, UpdateUserRequest,
    UpdatePermissionsRequest, DeleteUserRequest,
    CreateAgentRequest, DeleteAgentRequest,
    ProviderListResponse, ProviderInfo,
    SuccessResponse, ErrorResponse,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])
# Router separe pour /api/users (le prefixe /api/admin ne permet pas /api/users)
users_router = APIRouter(prefix="/api", tags=["admin"])


def _require_admin(request: Request, response: Response) -> dict | None:
    token = request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    user = get_user_from_token(token)
    if not user:
        response.status_code = 401
        return None
    if user["role"] != "admin":
        response.status_code = 403
        return None
    return user


@users_router.get("/users", response_model=UserListResponse)
def list_users(request: Request, response: Response):
    if not _require_admin(request, response):
        return {"users": [], "panels": [], "agents": []}
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, email, role, disabled, created_at, permissions FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    users = [{"id": r[0], "name": r[1], "email": r[2], "role": r[3],
              "disabled": bool(r[4]), "created_at": r[5],
              "permissions": json.loads(r[6]) if r[6] else {}} for r in rows]
    return {"users": users, "panels": PANELS, "agents": list_profiles()}


@users_router.get("/providers", response_model=ProviderListResponse)
def list_providers(request: Request):
    """Liste les fournisseurs LLM disponibles pour la création d'agents."""
    token = request.cookies.get("token") or request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not get_user_from_token(token):
        return {"providers": []}
    providers = [
        ProviderInfo(
            id=pid,
            label=p["label"],
            models=p["models"],
            base_url=p["base_url"],
            key_configured=bool(p.get("key_env") and os.environ.get(p["key_env"])),
        )
        for pid, p in PROVIDERS.items()
    ]
    return {"providers": providers}


@router.post("/user/create", response_model=SuccessResponse | ErrorResponse)
def create_user(body: CreateUserRequest, request: Request, response: Response):
    if not _require_admin(request, response):
        return {"error": "Accès refusé"}
    name, email, password, role = body.name.strip(), body.email.strip().lower(), body.password, body.role
    if not name or not email or not password:
        response.status_code = 400
        return {"error": "Tous les champs sont obligatoires"}
    if len(password) < 6:
        response.status_code = 400
        return {"error": "Mot de passe trop court"}
    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        response.status_code = 409
        return {"error": "Cet email est déjà utilisé"}
    if conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone():
        conn.close()
        response.status_code = 409
        return {"error": "Ce nom est déjà utilisé"}
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role, permissions) VALUES (?, ?, ?, ?, ?)",
        (name, email, hash_password(password), role, json.dumps(body.permissions.model_dump())),
    )
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/user/update", response_model=SuccessResponse)
def update_user(body: UpdateUserRequest, request: Request, response: Response):
    if not _require_admin(request, response):
        return {"success": False}
    conn = get_db()
    if body.role is not None:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (body.role, body.id))
    if body.disabled is not None:
        conn.execute("UPDATE users SET disabled = ? WHERE id = ?", (1 if body.disabled else 0, body.id))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/user/permissions", response_model=SuccessResponse)
def update_permissions(body: UpdatePermissionsRequest, request: Request, response: Response):
    if not _require_admin(request, response):
        return {"success": False}
    conn = get_db()
    conn.execute("UPDATE users SET permissions = ? WHERE id = ?",
                 (json.dumps(body.permissions.model_dump()), body.id))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/user/delete", response_model=SuccessResponse | ErrorResponse)
def delete_user(body: DeleteUserRequest, request: Request, response: Response):
    admin = _require_admin(request, response)
    if not admin:
        return {"error": "Accès refusé"}
    if body.id == admin["id"]:
        response.status_code = 400
        return {"error": "Impossible de se supprimer soi-même"}
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (body.id,))
    conn.execute("DELETE FROM users WHERE id = ?", (body.id,))
    conn.commit()
    conn.close()
    return {"success": True}


@router.post("/agent/create", response_model=SuccessResponse | ErrorResponse)
def create_agent(body: CreateAgentRequest, request: Request, response: Response):
    if not _require_admin(request, response):
        return {"error": "Accès refusé"}
    name = body.name.strip().lower().replace(" ", "-")
    if not name:
        response.status_code = 400
        return {"error": "Le nom est obligatoire"}
    existing = list_profiles()
    if name in existing:
        response.status_code = 409
        return {"error": f"L'agent '{name}' existe déjà"}

    # Resoudre le fournisseur LLM choisi
    provider = PROVIDERS.get(body.provider)
    if not provider:
        response.status_code = 400
        return {"error": f"Fournisseur inconnu: {body.provider}"}

    base_url = provider["base_url"]
    model = body.model.strip()
    if body.provider == "custom":
        base_url = body.base_url.strip()
        if not base_url or not model:
            response.status_code = 400
            return {"error": "Fournisseur custom : base_url et modèle sont obligatoires"}
    else:
        if model not in provider["models"]:
            response.status_code = 400
            return {"error": f"Modèle '{model}' non disponible chez {provider['label']}"}

    # Cle API du fournisseur (fallback : cle globale Hermes)
    api_key = ""
    if provider.get("key_env"):
        api_key = os.environ.get(provider["key_env"], "")

    if create_agent_profile(name, body.description, model, base_url, api_key, body.persona):
        AGENTS[name] = {"emoji": body.emoji, "color": body.color,
                        "desc": f"{body.description} [{provider['label']} · {model}]"}
        return {"success": True}
    response.status_code = 500
    return {"error": "Erreur lors de la création de l'agent"}


@router.post("/agent/delete", response_model=SuccessResponse | ErrorResponse)
def delete_agent(body: DeleteAgentRequest, request: Request, response: Response):
    if not _require_admin(request, response):
        return {"error": "Accès refusé"}
    name = body.name.strip()
    builtin = {"architect", "senior-dev", "code-reviewer", "qa-engineer", "devops", "orchestrator"}
    if name in builtin:
        response.status_code = 400
        return {"error": "Impossible de supprimer un agent intégré"}
    if delete_agent_profile(name):
        AGENTS.pop(name, None)
        return {"success": True}
    response.status_code = 500
    return {"error": "Erreur lors de la suppression"}
