# -*- coding: utf-8 -*-
"""Agent OS — Gestion de la base de donnees SQLite"""
import json, hashlib, secrets, sqlite3
from pathlib import Path
from config import DB_PATH


def init_db() -> None:
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


def get_db() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def generate_token() -> str:
    return secrets.token_hex(32)


def get_user_from_token(token: str | None) -> dict | None:
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


def get_user_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count


def check_agent_access(user: dict, agent: str) -> bool:
    if user["role"] == "admin":
        return True
    perms = user.get("permissions", {})
    allowed = perms.get("agents", [])
    return not allowed or agent in allowed
