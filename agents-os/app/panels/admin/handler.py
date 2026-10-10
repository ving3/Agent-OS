# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Administration
Gestion des utilisateurs (CRUD), permissions, creation/suppression d'agents.
"""
import json
import subprocess

from config import AGENTS, PANELS
from database import get_db, hash_password
from hermes_client import list_profiles as list_hermes_profiles


def handle_list_users(handler):
    """GET /api/users — Liste tous les utilisateurs (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    conn = get_db()
    rows = conn.execute(
        "SELECT id, name, email, role, disabled, created_at, permissions FROM users ORDER BY id"
    ).fetchall()
    conn.close()
    users = [{"id": r[0], "name": r[1], "email": r[2], "role": r[3], "disabled": bool(r[4]),
               "created_at": r[5], "permissions": json.loads(r[6]) if r[6] else {}} for r in rows]
    handler._send_json({"users": users, "panels": PANELS, "agents": list_hermes_profiles()})


def handle_get_user(handler, uid):
    """GET /admin/user/<id> — Detail d'un utilisateur (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    conn = get_db()
    row = conn.execute("SELECT id, name, email, role, disabled, created_at FROM users WHERE id = ?",
                       (uid,)).fetchone()
    conn.close()
    if row:
        handler._send_json({"id": row[0], "name": row[1], "email": row[2], "role": row[3],
                            "disabled": bool(row[4]), "created_at": row[5]})
    else:
        handler._send_json({"error": "User not found"}, 404)


def handle_create_user(handler, body):
    """POST /api/admin/user/create — Cree un utilisateur (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    name = body.get("name", "").strip()
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    role = body.get("role", "user")
    permissions = body.get("permissions", {})
    if not name or not email or not password:
        handler._send_json({"error": "Tous les champs sont obligatoires"}, 400)
        return
    if len(password) < 6:
        handler._send_json({"error": "Le mot de passe doit faire au moins 6 caracteres"}, 400)
        return
    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        handler._send_json({"error": "Cet email est deja utilise"}, 409)
        return
    if conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone():
        conn.close()
        handler._send_json({"error": "Ce nom est deja utilise"}, 409)
        return
    pwd_hash = hash_password(password)
    perms_json = json.dumps(permissions)
    conn.execute("INSERT INTO users (name, email, password_hash, role, permissions) VALUES (?, ?, ?, ?, ?)",
                 (name, email, pwd_hash, role, perms_json))
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    conn.close()
    handler._send_json({"success": True, "user": {"id": uid, "name": name, "email": email, "role": role}})


def handle_update_user_permissions(handler, body):
    """POST /api/admin/user/permissions — Modifie les permissions (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    uid = body.get("id")
    permissions = body.get("permissions", {})
    conn = get_db()
    conn.execute("UPDATE users SET permissions = ? WHERE id = ?", (json.dumps(permissions), uid))
    conn.commit()
    conn.close()
    handler._send_json({"success": True})


def handle_update_user(handler, body):
    """POST /api/admin/user/update — Modifie role/statut utilisateur (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    uid = body.get("id")
    conn = get_db()
    if "role" in body:
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (body["role"], uid))
    if "disabled" in body:
        conn.execute("UPDATE users SET disabled = ? WHERE id = ?", (1 if body["disabled"] else 0, uid))
    conn.commit()
    conn.close()
    handler._send_json({"success": True})


def handle_delete_user(handler, body, admin_user):
    """POST /api/admin/user/delete — Supprime un utilisateur (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    uid = body.get("id")
    if uid == admin_user["id"]:
        handler._send_json({"error": "Impossible de se supprimer soi-meme"}, 400)
        return
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
    conn.execute("DELETE FROM users WHERE id = ?", (uid,))
    conn.commit()
    conn.close()
    handler._send_json({"success": True})


def handle_create_agent(handler, body):
    """POST /api/admin/agent/create — Cree un agent via Hermes pod exec (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    name = body.get("name", "").strip().lower().replace(" ", "-")
    emoji = body.get("emoji", "\U0001F916")
    color = body.get("color", "#58a6ff")
    description = body.get("description", "")
    if not name:
        handler._send_json({"error": "Le nom est obligatoire"}, 400)
        return
    existing = list_hermes_profiles()
    if len(existing) >= 50:
        handler._send_json({"error": "Maximum 50 agents atteint"}, 400)
        return
    if name in existing:
        handler._send_json({"error": f"L'agent '{name}' existe deja"}, 409)
        return
    try:
        result = subprocess.run(
            ["kubectl", "exec", "-n", "ai", "deployment/hermes", "--",
             "sh", "-c",
             f"mkdir -p /opt/data/profiles/{name} && "
             f"cat > /opt/data/profiles/{name}/SOUL.md << 'SOUL'\n"
             f"# Agent {name}\n\n{description}\n\n"
             f"## Role\n\nAgent cree depuis Agentic OS Dashboard.\n"
             f"SOUL\n"
             f"cat > /opt/data/profiles/{name}/config.yaml << 'CFG'\n"
             f"model:\n  provider: openai\n  default: deepseek-v4-pro-260425\n"
             f"  base_url: https://ark.ap-southeast.bytepluses.com/api/coding/v3\n"
             f"CFG\n"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            handler._send_json({"error": f"Erreur creation: {result.stderr.strip()}"}, 500)
            return
        AGENTS[name] = {"emoji": emoji, "color": color, "desc": description}
        handler._send_json({"success": True, "agent": {"name": name, "emoji": emoji, "color": color, "description": description}})
    except Exception as e:
        handler._send_json({"error": f"Erreur creation agent: {e}"}, 500)


def handle_delete_agent(handler, body):
    """POST /api/admin/agent/delete — Supprime un agent via Hermes pod exec (admin only)."""
    admin = handler._require_admin()
    if not admin:
        return
    name = body.get("name", "").strip()
    if not name:
        handler._send_json({"error": "Nom requis"}, 400)
        return
    builtin = {"architect", "senior-dev", "code-reviewer", "qa-engineer", "devops", "orchestrator"}
    if name in builtin:
        handler._send_json({"error": "Impossible de supprimer un agent integre"}, 400)
        return
    try:
        result = subprocess.run(
            ["kubectl", "exec", "-n", "ai", "deployment/hermes", "--",
             "rm", "-rf", f"/opt/data/profiles/{name}"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            handler._send_json({"error": f"Erreur suppression: {result.stderr.strip()}"}, 500)
            return
        AGENTS.pop(name, None)
        handler._send_json({"success": True})
    except Exception as e:
        handler._send_json({"error": f"Erreur suppression agent: {e}"}, 500)
