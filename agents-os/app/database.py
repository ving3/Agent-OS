# -*- coding: utf-8 -*-
"""
Agentic OS — Gestion de la base de donnees SQLite (utilisateurs, sessions)
"""
import json
import sqlite3
import hashlib
import secrets
from pathlib import Path
from config import DB_PATH


def init_db():
    """Cree les tables si elles n'existent pas."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'user',
        created_at TEXT DEFAULT (datetime('now')),
        disabled INTEGER DEFAULT 0,
        permissions TEXT DEFAULT '{}'
    )""")
    try:
        conn.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()


def get_db():
    return sqlite3.connect(DB_PATH)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_hex(32)


def get_user_from_token(token: str) -> dict | None:
    if not token:
        return None
    conn = get_db()
    cur = conn.execute(
        "SELECT u.id, u.name, u.email, u.role, u.disabled, u.permissions FROM users u "
        "JOIN sessions s ON u.id = s.user_id WHERE s.token = ?", (token,))
    row = cur.fetchone()
    conn.close()
    if row and not row[4]:
        perms = json.loads(row[5]) if row[5] else {}
        return {"id": row[0], "name": row[1], "email": row[2], "role": row[3], "permissions": perms}
    return None


def get_user_by_id(uid: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT id, name, email, role, disabled, permissions, created_at FROM users WHERE id = ?",
                       (uid,)).fetchone()
    conn.close()
    if row:
        perms = json.loads(row[5]) if row[5] else {}
        return {"id": row[0], "name": row[1], "email": row[2], "role": row[3],
                "disabled": bool(row[4]), "permissions": perms, "created_at": row[6]}
    return None


def get_user_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def check_panel_access(user: dict, panel: str) -> bool:
    if user["role"] == "admin":
        return True
    perms = user.get("permissions", {})
    allowed_panels = perms.get("panels", [])
    return panel in allowed_panels


def check_agent_access(user: dict, agent: str) -> bool:
    if user["role"] == "admin":
        return True
    perms = user.get("permissions", {})
    allowed_agents = perms.get("agents", [])
    return not allowed_agents or agent in allowed_agents
