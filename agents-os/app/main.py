"""
Agentic OS â€” Dashboard de gestion des agents IA
Authentification + Control Panel + Chat Agents + Kanban + Memoire + Skills
Premier inscrit = administrateur (comme OpenWebUI)
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import os
import secrets
import sqlite3
import time
import threading
from http.cookies import SimpleCookie
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import httpx

# --- Configuration ---
DATA_DIR = os.environ.get("DATA_DIR", "/data")
HERMES_API_URL = os.environ.get("HERMES_API_URL", "http://hermes:8777")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
PROFILES_DIR = os.environ.get("PROFILES_DIR", "/opt/data/profiles")
SKILLS_DIR = os.environ.get("SKILLS_DIR", "/opt/data/skills")
HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("BRIDGE_PORT", "8686"))

os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "agentic_os.db")

# --- Base de donnees utilisateurs ---
PANELS = ["overview", "canvas", "graph", "chat", "memory", "skills", "kanban", "admin"]

def init_db():
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
    # Add permissions column if missing (migration)
    try:
        conn.execute("ALTER TABLE users ADD COLUMN permissions TEXT DEFAULT '{}'")
    except sqlite3.OperationalError:
        pass  # Column already exists
    conn.execute("""CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        created_at TEXT DEFAULT (datetime('now')),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )""")
    conn.commit()
    conn.close()

init_db()

# --- Helpers ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_token() -> str:
    return secrets.token_hex(32)

def get_db():
    return sqlite3.connect(DB_PATH)

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
    row = conn.execute("SELECT id, name, email, role, disabled, permissions, created_at FROM users WHERE id = ?", (uid,)).fetchone()
    conn.close()
    if row:
        perms = json.loads(row[5]) if row[5] else {}
        return {"id": row[0], "name": row[1], "email": row[2], "role": row[3], "disabled": bool(row[4]), "permissions": perms, "created_at": row[6]}
    return None


def check_panel_access(user: dict, panel: str) -> bool:
    """Verifie si un utilisateur a acces a un panneau."""
    if user["role"] == "admin":
        return True
    perms = user.get("permissions", {})
    allowed_panels = perms.get("panels", [])
    return panel in allowed_panels


def check_agent_access(user: dict, agent: str) -> bool:
    """Verifie si un utilisateur a acces a un agent."""
    if user["role"] == "admin":
        return True
    perms = user.get("permissions", {})
    allowed_agents = perms.get("agents", [])
    return not allowed_agents or agent in allowed_agents

def get_user_count() -> int:
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count

# --- Agents disponibles ---
AGENTS = {
    "architect": {"emoji": "\U0001F3DB\uFE0F", "color": "#1f6feb", "desc": "Conception systeme, ADR, choix technologiques"},
    "senior-dev": {"emoji": "\U0001F4BB", "color": "#238636", "desc": "Implementation full-stack, APIs, debugging"},
    "code-reviewer": {"emoji": "\U0001F50D", "color": "#8957e5", "desc": "Audit securite, qualite, bonnes pratiques"},
    "qa-engineer": {"emoji": "\U0001F9EA", "color": "#d29922", "desc": "Tests, TDD, chasse aux bugs"},
    "devops": {"emoji": "\u2699\uFE0F", "color": "#da3633", "desc": "CI/CD, conteneurs, infrastructure"},
}

stats = {"start_time": time.time(), "total_calls": 0, "calls_per_agent": {}, "errors": 0}
stats_lock = threading.Lock()
http_client = httpx.Client(timeout=120.0)


def call_hermes_api(profile: str, messages: list) -> str:
    headers = {"Content-Type": "application/json"}
    if HERMES_API_KEY:
        headers["Authorization"] = f"Bearer {HERMES_API_KEY}"
    system_prompt = ""
    user_msgs = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            system_prompt = content
        elif role == "user":
            user_msgs.append(content)
    api_msgs = []
    if system_prompt:
        api_msgs.append({"role": "system", "content": f"Tu es l'agent {profile}. {system_prompt}"})
    else:
        api_msgs.append({"role": "system", "content": f"Tu es l'agent {profile}. Reponds en francais."})
    for c in user_msgs:
        api_msgs.append({"role": "user", "content": c})
    try:
        resp = http_client.post(
            f"{HERMES_API_URL}/v1/chat/completions",
            headers=headers,
            json={"model": "hermes-agent", "messages": api_msgs},
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "[Erreur] Reponse vide")
    except httpx.HTTPStatusError as e:
        return f"[Erreur] API Hermes: HTTP {e.response.status_code}"
    except Exception as e:
        return f"[Erreur] {e}"


def get_agent_memory(profile_name: str) -> str:
    mem_file = Path(PROFILES_DIR) / profile_name / "memories" / "memory.md"
    if mem_file.exists():
        return mem_file.read_text()
    return ""


def list_skills() -> list[dict]:
    skills = []
    sp = Path(SKILLS_DIR)
    if sp.is_dir():
        for sf in sp.rglob("SKILL.md"):
            rel = sf.parent.relative_to(sp)
            content = sf.read_text()
            name, desc = "", ""
            in_front = False
            for line in content.split("\n"):
                if line.strip() == "---":
                    in_front = not in_front
                    continue
                if in_front:
                    if line.startswith("name:"):
                        name = line.split(":", 1)[1].strip()
                    elif line.startswith("description:"):
                        desc = line.split(":", 1)[1].strip().strip('"')
            skills.append({"name": name or sf.parent.name, "path": str(rel), "description": desc})
    return skills


def list_profiles() -> list[str]:
    pp = Path(PROFILES_DIR)
    if pp.is_dir():
        return sorted(p.name for p in pp.iterdir() if p.is_dir())
    return []


# --- Serveur HTTP ---
class AgenticOSHandler(BaseHTTPRequestHandler):

    def _send_json(self, data: dict, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _send_html(self, html: str, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(html.encode())

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length))
        return {}

    def _get_token(self) -> str | None:
        raw = self.headers.get("Cookie", "")
        if "token=" in raw:
            for part in raw.split(";"):
                part = part.strip()
                if part.startswith("token="):
                    return part[6:]
        return None

    def _get_user(self) -> dict | None:
        return get_user_from_token(self._get_token())

    def _require_auth(self) -> dict | None:
        user = self._get_user()
        if not user:
            self._send_html(LOGIN_PAGE, 401)
        return user

    def _require_admin(self) -> dict | None:
        user = self._require_auth()
        if user and user["role"] != "admin":
            self._send_html("<h1>403 Acces interdit</h1><p>Vous devez etre administrateur.</p>", 403)
            return None
        return user

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, Cookie")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        params = parse_qs(parsed.query)

        # --- Pages publiques ---
        if path == "/health":
            self._send_json({"status": "ok"})
            return

        if path in ("", "/login"):
            if self._get_user():
                self._redirect("/dashboard")
            else:
                self._send_html(LOGIN_PAGE)
            return

        if path == "/signup":
            if self._get_user():
                self._redirect("/dashboard")
            else:
                self._send_html(SIGNUP_PAGE)
            return

        if path == "/logout":
            token = self._get_token()
            if token:
                conn = get_db()
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
                conn.commit()
                conn.close()
            self.send_response(302)
            self.send_header("Set-Cookie", "token=; Max-Age=0; Path=/; HttpOnly; SameSite=Lax")
            self.send_header("Location", "/login")
            self.end_headers()
            return

        # --- Pages protegees ---
        user = self._require_auth()
        if not user:
            return

        if path == "/dashboard":
            self._send_html(self._render_dashboard(user))
            return

        if path == "/admin":
            user = self._require_auth()
            if user:
                self._send_html(self._render_dashboard(user, "admin"))
            return

        if path.startswith("/admin/user/"):
            admin = self._require_admin()
            if not admin:
                return
            uid = path.split("/")[-1]
            conn = get_db()
            row = conn.execute("SELECT id, name, email, role, disabled, created_at FROM users WHERE id = ?", (uid,)).fetchone()
            conn.close()
            if row:
                self._send_json({"id": row[0], "name": row[1], "email": row[2], "role": row[3], "disabled": bool(row[4]), "created_at": row[5]})
            else:
                self._send_json({"error": "User not found"}, 404)
            return

        # --- API ---
        if path == "/api/status":
            with stats_lock:
                uptime = time.time() - stats["start_time"]
                self._send_json({
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
            return

        if path == "/api/skills":
            self._send_json({"skills": list_skills()})
            return

        if path == "/api/profiles":
            user = self._get_user()
            profiles = []
            for name in list_profiles():
                if not check_agent_access(user, name) if user else True:
                    continue
                mem = get_agent_memory(name)
                ai = AGENTS.get(name, {})
                profiles.append({
                    "name": name, "emoji": ai.get("emoji", "\U0001F916"),
                    "color": ai.get("color", "#58a6ff"),
                    "description": ai.get("desc", ""), "memory": mem, "has_memory": bool(mem),
                })
            self._send_json({"profiles": profiles})
            return

        if path.startswith("/api/profile/"):
            pname = path.split("/")[-1]
            mem = get_agent_memory(pname)
            ai = AGENTS.get(pname, {})
            self._send_json({"name": pname, "emoji": ai.get("emoji", "\U0001F916"),
                             "description": ai.get("desc", ""), "memory": mem})
            return

        if path == "/api/users":
            admin = self._require_admin()
            if not admin:
                return
            conn = get_db()
            rows = conn.execute("SELECT id, name, email, role, disabled, created_at, permissions FROM users ORDER BY id").fetchall()
            conn.close()
            users = [{"id": r[0], "name": r[1], "email": r[2], "role": r[3], "disabled": bool(r[4]), "created_at": r[5],
                      "permissions": json.loads(r[6]) if r[6] else {}} for r in rows]
            self._send_json({"users": users, "panels": PANELS, "agents": list_profiles()})
            return

        if path == "/v1/models":
            models = [{"id": f"hermes-{k}", "object": "model", "created": int(time.time()), "owned_by": "hermes"}
                      for k in AGENTS]
            self._send_json({"object": "list", "data": models})
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        # --- Auth ---
        if path == "/api/login":
            body = self._read_body()
            email = body.get("email", "").strip().lower()
            password = body.get("password", "")
            conn = get_db()
            row = conn.execute("SELECT id, name, email, role, disabled FROM users WHERE email = ?", (email,)).fetchone()
            if not row or row[4]:
                conn.close()
                self._send_json({"error": "Email ou mot de passe incorrect"}, 401)
                return
            if row[3] == "pending":
                conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (row[0],))
                conn.commit()
                row = (row[0], row[1], row[2], "admin", 0)
            pwd_hash = hash_password(password)
            stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (row[0],)).fetchone()[0]
            if stored != pwd_hash:
                conn.close()
                self._send_json({"error": "Email ou mot de passe incorrect"}, 401)
                return
            token = generate_token()
            conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row[0]))
            conn.commit()
            conn.close()
            self._send_json({
                "token": token, "user": {"id": row[0], "name": row[1], "email": row[2], "role": row[3]}
            })
            return

        if path == "/api/signup":
            body = self._read_body()
            name = body.get("name", "").strip()
            email = body.get("email", "").strip().lower()
            password = body.get("password", "")
            if not name or not email or not password:
                self._send_json({"error": "Tous les champs sont obligatoires"}, 400)
                return
            if len(password) < 6:
                self._send_json({"error": "Le mot de passe doit faire au moins 6 caracteres"}, 400)
                return
            conn = get_db()
            name = name.strip()
            email = email.strip().lower()
            existing_email = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing_email:
                conn.close()
                self._send_json({"error": "Cet email est deja utilise"}, 409)
                return
            existing_name = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
            if existing_name:
                conn.close()
                self._send_json({"error": "Ce nom est deja utilise"}, 409)
                return
            count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            role = "admin" if count == 0 else "user"
            pwd_hash = hash_password(password)
            conn.execute("INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
                         (name, email, pwd_hash, role))
            conn.commit()
            uid = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
            token = generate_token()
            conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, uid))
            conn.commit()
            conn.close()
            self._send_json({
                "token": token, "user": {"id": uid, "name": name, "email": email, "role": role}
            })
            return

        # --- Admin API ---
        if path == "/api/admin/user/create":
            admin = self._require_admin()
            if not admin:
                return
            body = self._read_body()
            name = body.get("name", "").strip()
            email = body.get("email", "").strip().lower()
            password = body.get("password", "")
            role = body.get("role", "user")
            permissions = body.get("permissions", {})
            if not name or not email or not password:
                self._send_json({"error": "Tous les champs sont obligatoires"}, 400)
                return
            if len(password) < 6:
                self._send_json({"error": "Le mot de passe doit faire au moins 6 caracteres"}, 400)
                return
            conn = get_db()
            name = name.strip()
            email = email.strip().lower()
            existing_email = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing_email:
                conn.close()
                self._send_json({"error": "Cet email est deja utilise"}, 409)
                return
            existing_name = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
            if existing_name:
                conn.close()
                self._send_json({"error": "Ce nom est deja utilise"}, 409)
                return
            pwd_hash = hash_password(password)
            perms_json = json.dumps(permissions)
            conn.execute("INSERT INTO users (name, email, password_hash, role, permissions) VALUES (?, ?, ?, ?, ?)",
                         (name, email, pwd_hash, role, perms_json))
            conn.commit()
            uid = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
            conn.close()
            self._send_json({"success": True, "user": {"id": uid, "name": name, "email": email, "role": role}})
            return

        if path == "/api/admin/user/permissions":
            admin = self._require_admin()
            if not admin:
                return
            body = self._read_body()
            uid = body.get("id")
            permissions = body.get("permissions", {})
            conn = get_db()
            perms_json = json.dumps(permissions)
            conn.execute("UPDATE users SET permissions = ? WHERE id = ?", (perms_json, uid))
            conn.commit()
            conn.close()
            self._send_json({"success": True})
            return

        if path == "/api/admin/user/update":
            admin = self._require_admin()
            if not admin:
                return
            body = self._read_body()
            uid = body.get("id")
            conn = get_db()
            if "role" in body:
                conn.execute("UPDATE users SET role = ? WHERE id = ?", (body["role"], uid))
            if "disabled" in body:
                conn.execute("UPDATE users SET disabled = ? WHERE id = ?", (1 if body["disabled"] else 0, uid))
            conn.commit()
            conn.close()
            self._send_json({"success": True})
            return

        if path == "/api/admin/user/delete":
            admin = self._require_admin()
            if not admin:
                return
            body = self._read_body()
            uid = body.get("id")
            if uid == admin["id"]:
                self._send_json({"error": "Impossible de se supprimer soi-meme"}, 400)
                return
            conn = get_db()
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
            conn.execute("DELETE FROM users WHERE id = ?", (uid,))
            conn.commit()
            conn.close()
            self._send_json({"success": True})
            return

        if path == "/api/admin/agent/create":
            admin = self._require_admin()
            if not admin:
                return
            body = self._read_body()
            name = body.get("name", "").strip().lower().replace(" ", "-")
            emoji = body.get("emoji", "\U0001F916")
            color = body.get("color", "#58a6ff")
            description = body.get("description", "")
            if not name:
                self._send_json({"error": "Le nom est obligatoire"}, 400)
                return
            # Check max 50 agents
            existing = list_profiles()
            if len(existing) >= 50:
                self._send_json({"error": "Maximum 50 agents atteint"}, 400)
                return
            if name in existing:
                self._send_json({"error": f"L'agent '{name}' existe deja"}, 409)
                return
            # Create agent profile via Hermes pod exec
            import subprocess
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
                    self._send_json({"error": f"Erreur creation: {result.stderr.strip()}"}, 500)
                    return
                # Add to AGENTS dict (runtime only)
                AGENTS[name] = {"emoji": emoji, "color": color, "desc": description}
                self._send_json({"success": True, "agent": {"name": name, "emoji": emoji, "color": color, "description": description}})
            except Exception as e:
                self._send_json({"error": f"Erreur creation agent: {e}"}, 500)
            return

        if path == "/api/admin/agent/delete":
            admin = self._require_admin()
            if not admin:
                return
            body = self._read_body()
            name = body.get("name", "").strip()
            if not name:
                self._send_json({"error": "Nom requis"}, 400)
                return
            # Prevent deleting built-in agents
            builtin = {"architect", "senior-dev", "code-reviewer", "qa-engineer", "devops", "orchestrator"}
            if name in builtin:
                self._send_json({"error": "Impossible de supprimer un agent integre"}, 400)
                return
            import subprocess
            try:
                result = subprocess.run(
                    ["kubectl", "exec", "-n", "ai", "deployment/hermes", "--",
                     "rm", "-rf", f"/opt/data/profiles/{name}"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0:
                    self._send_json({"error": f"Erreur suppression: {result.stderr.strip()}"}, 500)
                    return
                # Remove from AGENTS dict if present
                AGENTS.pop(name, None)
                self._send_json({"success": True})
            except Exception as e:
                self._send_json({"error": f"Erreur suppression agent: {e}"}, 500)
            return

        # --- Chat ---
        if path == "/v1/chat/completions":
            body = self._read_body()
            model = body.get("model", "hermes-agent")
            messages = body.get("messages", [])
            profile = model.replace("hermes-", "", 1) if model.startswith("hermes-") else "devops"
            with stats_lock:
                stats["total_calls"] += 1
                stats["calls_per_agent"][profile] = stats["calls_per_agent"].get(profile, 0) + 1
            result = call_hermes_api(profile, messages)
            is_err = result.startswith("[Erreur]")
            if is_err:
                with stats_lock:
                    stats["errors"] += 1
            self._send_json({
                "id": f"chatcmpl-{int(time.time())}", "object": "chat.completion",
                "created": int(time.time()), "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": result},
                             "finish_reason": "error" if is_err else "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            })
            return

        if path == "/api/chat":
            body = self._read_body()
            profile = body.get("profile", "devops")
            message = body.get("message", "")
            result = call_hermes_api(profile, [{"role": "user", "content": message}])
            self._send_json({"response": result})
            return

        self._send_json({"error": "Not found"}, 404)

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _render_dashboard(self, user: dict, panel: str = "overview") -> str:
        html = DASHBOARD_HTML.replace("{{USER_NAME}}", html_mod.escape(user["name"])) \
            .replace("{{USER_ROLE}}", html_mod.escape(user["role"])) \
            .replace("{{USER_EMAIL}}", html_mod.escape(user["email"]))
        # Set active panel
        html = html.replace('data-panel="overview" class="nav-item active"', 'data-panel="overview" class="nav-item"')
        html = html.replace(f'data-panel="{panel}" class="nav-item"', f'data-panel="{panel}" class="nav-item active"')
        html = html.replace('class="panel active" id="panel-overview"', 'class="panel" id="panel-overview"')
        html = html.replace(f'class="panel" id="panel-{panel}"', f'class="panel active" id="panel-{panel}"')
        return html

    def _render_admin(self, user: dict) -> str:
        return ADMIN_HTML.replace("{{USER_NAME}}", html_mod.escape(user["name"]))


# ========== PAGES HTML ==========

LOGIN_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agentic OS â€” Connexion</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#0d1117; color:#c9d1d9; min-height:100vh;
  display:flex; align-items:center; justify-content:center; }
.auth-card { background:#161b22; border:1px solid #30363d; border-radius:12px;
  padding:40px; width:400px; max-width:90vw; }
.auth-card h1 { font-size:22px; color:#58a6ff; margin-bottom:8px; text-align:center; }
.auth-card .sub { color:#8b949e; font-size:13px; margin-bottom:24px; text-align:center; }
.form-group { margin-bottom:16px; }
.form-group label { display:block; font-size:12px; color:#8b949e; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px; }
.form-group input { width:100%; background:#0d1117; border:1px solid #30363d; border-radius:6px;
  padding:10px 12px; color:#c9d1d9; font-size:14px; outline:none; font-family:inherit; }
.form-group input:focus { border-color:#58a6ff; }
.btn { width:100%; padding:10px; border-radius:6px; border:none; font-size:14px;
  font-weight:600; cursor:pointer; font-family:inherit; }
.btn-primary { background:#238636; color:#fff; }
.btn-primary:hover { background:#2ea043; }
.btn:disabled { background:#30363d; color:#484f58; cursor:not-allowed; }
.error { background:#da363322; border:1px solid #da3633; border-radius:6px;
  padding:10px; color:#f85149; font-size:13px; margin-bottom:16px; display:none; }
.footer { text-align:center; margin-top:20px; font-size:13px; color:#8b949e; }
.footer a { color:#58a6ff; text-decoration:none; }
.footer a:hover { text-decoration:underline; }
.loader { display:inline-block; width:16px; height:16px; border:2px solid #484f58;
  border-top-color:#58a6ff; border-radius:50%; animation:spin 0.6s linear; vertical-align:middle; }
@keyframes spin { to { transform:rotate(360deg); } }
</style></head>
<body>
<div class="auth-card">
  <h1>âš¡ Agentic OS</h1>
  <div class="sub">Connectez-vous pour acceder au tableau de bord</div>
  <div class="error" id="error"></div>
  <form id="loginForm" onsubmit="return doLogin(event)">
    <div class="form-group">
      <label>Email</label>
      <input type="email" id="email" placeholder="ex: admin@local.home" required autofocus>
    </div>
    <div class="form-group">
      <label>Mot de passe</label>
      <input type="password" id="password" placeholder="Votre mot de passe" required>
    </div>
    <button type="submit" class="btn btn-primary" id="submitBtn">Se connecter</button>
  </form>
  <div class="footer">Pas encore de compte ? <a href="/signup">Creer un compte</a></div>
</div>
<script>
async function doLogin(e) {
  e.preventDefault(); const btn=document.getElementById('submitBtn'); const err=document.getElementById('error');
  btn.disabled=true; btn.innerHTML='<span class="loader"></span>'; err.style.display='none';
  try {
    const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({email:document.getElementById('email').value,password:document.getElementById('password').value})});
    const d=await r.json();
    if(d.error) { err.textContent=d.error; err.style.display='block'; btn.disabled=false; btn.textContent='Se connecter'; return; }
    document.cookie='token='+d.token+'; Path=/; SameSite=Lax';
    window.location.href='/dashboard';
  } catch(e) { err.textContent='Erreur de connexion'; err.style.display='block'; btn.disabled=false; btn.textContent='Se connecter'; }
  return false;
}
</script>
</body></html>"""

SIGNUP_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agentic OS â€” Inscription</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
  background:#0d1117; color:#c9d1d9; min-height:100vh;
  display:flex; align-items:center; justify-content:center; }
.auth-card { background:#161b22; border:1px solid #30363d; border-radius:12px;
  padding:40px; width:400px; max-width:90vw; }
.auth-card h1 { font-size:22px; color:#58a6ff; margin-bottom:8px; text-align:center; }
.auth-card .sub { color:#8b949e; font-size:13px; margin-bottom:24px; text-align:center; }
.form-group { margin-bottom:16px; }
.form-group label { display:block; font-size:12px; color:#8b949e; margin-bottom:6px; text-transform:uppercase; letter-spacing:0.5px; }
.form-group input { width:100%; background:#0d1117; border:1px solid #30363d; border-radius:6px;
  padding:10px 12px; color:#c9d1d9; font-size:14px; outline:none; font-family:inherit; }
.form-group input:focus { border-color:#58a6ff; }
.btn { width:100%; padding:10px; border-radius:6px; border:none; font-size:14px;
  font-weight:600; cursor:pointer; font-family:inherit; }
.btn-primary { background:#238636; color:#fff; }
.btn-primary:hover { background:#2ea043; }
.error { background:#da363322; border:1px solid #da3633; border-radius:6px;
  padding:10px; color:#f85149; font-size:13px; margin-bottom:16px; display:none; }
.footer { text-align:center; margin-top:20px; font-size:13px; color:#8b949e; }
.footer a { color:#58a6ff; text-decoration:none; }
.footer a:hover { text-decoration:underline; }
.info { background:#1f6feb22; border:1px solid #1f6feb; border-radius:6px;
  padding:10px; color:#58a6ff; font-size:12px; margin-bottom:16px; }
</style></head>
<body>
<div class="auth-card">
  <h1>âš¡ Agentic OS</h1>
  <div class="sub" id="subtitle">Creez votre compte</div>
  <div class="error" id="error"></div>
  <div class="info" id="firstUserInfo">Premier compte = administrateur</div>
  <form id="signupForm" onsubmit="return doSignup(event)">
    <div class="form-group">
      <label>Nom</label>
      <input type="text" id="name" placeholder="Votre nom" required autofocus>
    </div>
    <div class="form-group">
      <label>Email</label>
      <input type="email" id="email" placeholder="ex: user@local.home" required>
    </div>
    <div class="form-group">
      <label>Mot de passe</label>
      <input type="password" id="password" placeholder="Minimum 6 caracteres" required minlength="6">
    </div>
    <button type="submit" class="btn btn-primary" id="submitBtn">Creer mon compte</button>
  </form>
  <div class="footer">Deja un compte ? <a href="/login">Se connecter</a></div>
</div>
<script>
async function doSignup(e) {
  e.preventDefault(); const btn=document.getElementById('submitBtn'); const err=document.getElementById('error');
  btn.disabled=true; btn.innerHTML='<span class="loader"></span>'; err.style.display='none';
  try {
    const r=await fetch('/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name:document.getElementById('name').value,email:document.getElementById('email').value,password:document.getElementById('password').value})});
    const d=await r.json();
    if(d.error) { err.textContent=d.error; err.style.display='block'; btn.disabled=false; btn.textContent='Creer mon compte'; return; }
    document.cookie='token='+d.token+'; Path=/; SameSite=Lax';
    window.location.href='/dashboard';
  } catch(e) { err.textContent='Erreur'; err.style.display='block'; btn.disabled=false; btn.textContent='Creer mon compte'; }
  return false;
}
</script>
</body></html>"""


DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agentic OS — Dashboard</title>
<style>
:root{--bg:#0d1117;--surface:#161b22;--surface2:#1c2333;--border:#30363d;--text:#c9d1d9;--text2:#8b949e;--text3:#484f58;--blue:#58a6ff;--green:#3fb950;--purple:#bc8cff;--orange:#d29922;--red:#f85149;--cyan:#39d2c0}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.app{display:flex;min-height:100vh}
.sidebar{width:240px;min-width:240px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;position:sticky;top:0;height:100vh}
.sidebar-logo{padding:20px 20px 16px;border-bottom:1px solid var(--border)}
.sidebar-logo h1{font-size:18px;font-weight:700;color:var(--blue);display:flex;align-items:center;gap:8px}
.sidebar-logo .ver{font-size:10px;color:var(--text3);margin-top:2px}
.sidebar-nav{padding:12px 10px;flex:1}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;cursor:pointer;color:var(--text2);font-size:13px;font-weight:500;margin-bottom:2px;border:none;background:none;width:100%;text-align:left;transition:all 0.15s}
.nav-item:hover{background:var(--surface2);color:var(--text)}
.nav-item.active{background:var(--blue);color:#fff}
.nav-item .icon{font-size:17px;width:22px;text-align:center}
.nav-item .badge{margin-left:auto;background:var(--border);color:var(--text2);font-size:10px;padding:2px 7px;border-radius:10px}
.sidebar-footer{padding:12px 20px;border-top:1px solid var(--border);font-size:11px;color:var(--text3)}
.sidebar-footer .user-info{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.sidebar-footer .user-info .avatar{width:28px;height:28px;border-radius:50%;background:var(--blue);display:flex;align-items:center;justify-content:center;font-size:12px;color:#000;font-weight:700}
.sidebar-footer a{color:var(--text2);text-decoration:none;display:block;padding:4px 0}
.sidebar-footer a:hover{color:var(--text)}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.topbar .page-title{font-size:15px;font-weight:600}
.topbar .stats{display:flex;gap:20px;margin-left:auto}
.stat{text-align:center}.stat .val{font-size:18px;font-weight:700;color:var(--blue)}.stat .lbl{font-size:10px;color:var(--text3);text-transform:uppercase}
.content{flex:1;overflow-y:auto;padding:24px}
.panel{display:none}.panel.active{display:block}

/* Dashboard cards */
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}
.card{background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;transition:border-color 0.2s}
.card:hover{border-color:var(--blue)}
.card-header{display:flex;align-items:center;gap:12px;padding:16px 20px;border-bottom:1px solid var(--border)}
.card-avatar{width:42px;height:42px;border-radius:10px;display:flex;align-items:center;justify-content:center;font-size:20px;flex-shrink:0}
.card-title{font-size:14px;font-weight:600}.card-subtitle{font-size:11px;color:var(--text2)}
.card-body{padding:16px 20px}
.chat-log{min-height:100px;max-height:250px;overflow-y:auto;margin-bottom:12px;font-size:12px}
.chat-msg{margin-bottom:8px;padding:8px 12px;border-radius:6px;max-width:90%;word-break:break-word}
.chat-msg.user{background:rgba(88,166,255,0.1);color:var(--blue);margin-left:auto;text-align:right}
.chat-msg.agent{background:var(--surface2);border-left:2px solid var(--border)}
.chat-msg.error{background:rgba(248,81,73,0.1);color:var(--red)}
.chat-input-row{display:flex;gap:8px}
.chat-input-row input{flex:1;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 12px;color:var(--text);font-family:inherit;font-size:12px;outline:none}
.chat-input-row input:focus{border-color:var(--blue)}
.chat-input-row button{background:var(--blue);color:#000;border:none;border-radius:6px;padding:8px 14px;font-size:12px;cursor:pointer;font-weight:600;font-family:inherit}
.chat-input-row button:disabled{background:var(--border);color:var(--text3);cursor:not-allowed}
.status-dot{display:inline-flex;align-items:center;gap:6px;padding:3px 10px;border-radius:12px;font-size:10px;font-weight:500}
.status-dot.online{background:rgba(63,185,80,0.1);color:var(--green)}
.status-dot .pulse{width:7px;height:7px;border-radius:50%;background:currentColor}

/* Canvas - agent terminals grid */
.canvas-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(420px,1fr));gap:16px;height:calc(100vh - 160px);overflow-y:auto}
.canvas-agent{background:var(--surface);border:1px solid var(--border);border-radius:10px;display:flex;flex-direction:column;height:380px}
.canvas-agent .ca-header{display:flex;align-items:center;gap:10px;padding:10px 14px;border-bottom:1px solid var(--border);font-size:12px;font-weight:600;flex-shrink:0}
.canvas-agent .ca-log{flex:1;overflow-y:auto;padding:10px 14px;font-size:11px;background:var(--bg);font-family:'SF Mono','Fira Code',monospace}
.canvas-agent .ca-log .line{color:var(--text2);margin-bottom:2px;white-space:pre-wrap;word-break:break-word}
.canvas-agent .ca-log .line.user{color:var(--blue)}.canvas-agent .ca-log .line.agent{color:var(--green)}.canvas-agent .ca-log .line.cmd{color:var(--orange)}
.canvas-agent .ca-log .line.info{color:var(--text3)}.canvas-agent .ca-log .line.done{color:var(--cyan);font-weight:600}
.canvas-agent .ca-input{display:flex;padding:8px 14px;border-top:1px solid var(--border);gap:6px;flex-shrink:0}
.canvas-agent .ca-input input{flex:1;background:var(--bg);border:1px solid var(--border);border-radius:4px;padding:6px 10px;color:var(--text);font-size:11px;font-family:monospace;outline:none}
.canvas-agent .ca-input input:focus{border-color:var(--blue)}
.canvas-agent .ca-input button{background:var(--blue);color:#000;border:none;border-radius:4px;padding:6px 10px;font-size:11px;cursor:pointer;font-weight:600}

/* Graph visualization */
.graph-container{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:24px;min-height:400px}
.graph-svg{width:100%;height:400px}
.graph-node{fill:var(--surface2);stroke:var(--border);stroke-width:2;transition:all 0.3s;cursor:pointer}
.graph-node:hover{stroke:var(--blue);filter:drop-shadow(0 0 8px rgba(88,166,255,0.3))}
.graph-node.done{stroke:var(--green)}.graph-node.progress{stroke:var(--orange);stroke-dasharray:5,3}.graph-node.todo{stroke:var(--text3)}
.graph-label{fill:var(--text);font-size:11px;font-weight:500;text-anchor:middle;pointer-events:none}
.graph-label.sub{fill:var(--text3);font-size:9px;text-anchor:middle;pointer-events:none}
.graph-edge{stroke:var(--border);stroke-width:2;fill:none;marker-end:url(#arrow)}
.graph-edge.active{stroke:var(--blue);stroke-width:3}

/* Memory & Skills */
.memory-card{background:var(--surface);border:1px solid var(--border);border-radius:10px;margin-bottom:16px;overflow:hidden}
.memory-card .mem-header{display:flex;align-items:center;gap:12px;padding:14px 20px;border-bottom:1px solid var(--border);cursor:pointer}
.memory-card .mem-header:hover{background:var(--surface2)}
.memory-card .mem-body{display:none;padding:20px}.memory-card.open .mem-body{display:block}
.memory-card .mem-text{background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:14px;min-height:60px;white-space:pre-wrap;font-size:12px;color:var(--text2)}
.skills-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.skill-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:16px;transition:all 0.15s}
.skill-card:hover{border-color:var(--blue);transform:translateY(-1px)}
.skill-card .skill-name{font-size:13px;font-weight:600;margin-bottom:4px}
.skill-card .skill-path{font-size:10px;color:var(--text3);margin-bottom:6px}
.skill-card .skill-desc{font-size:11px;color:var(--text2)}

/* Kanban */
.kanban{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;min-height:300px}
.kanban-col{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px}
.kanban-col h3{font-size:12px;color:var(--text2);text-transform:uppercase;margin-bottom:12px;display:flex;align-items:center;gap:6px}
.kanban-col .count{font-size:10px;background:var(--border);padding:2px 8px;border-radius:10px}
.kanban-item{background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px;margin-bottom:8px;cursor:pointer;font-size:12px;transition:border-color 0.15s}
.kanban-item:hover{border-color:var(--blue)}
.kanban-item .ki-agent{font-size:10px;color:var(--blue);margin-bottom:4px}
.kanban-item .ki-title{font-weight:600;margin-bottom:4px}
.kanban-item .ki-meta{font-size:10px;color:var(--text3)}

@media(max-width:768px){.sidebar{width:60px;min-width:60px}.sidebar-logo h1 span,.nav-item span:not(.icon),.sidebar-footer .user-info span,.sidebar-footer a span{display:none}.canvas-grid{grid-template-columns:1fr}.kanban{grid-template-columns:1fr}}
</style></head>
<body>
<div class="app">
<aside class="sidebar">
<div class="sidebar-logo"><h1>⚡<span> Agentic OS</span></h1><div class="ver">v2.1</div></div>
<nav class="sidebar-nav">
<button class="nav-item active" data-panel="overview"><span class="icon">📊</span><span>Dashboard</span></button>
<button class="nav-item" data-panel="canvas"><span class="icon">🖥️</span><span>Canvas</span><span class="badge">5</span></button>
<button class="nav-item" data-panel="graph"><span class="icon">🔗</span><span>Graphe</span></button>
<button class="nav-item" data-panel="chat"><span class="icon">💬</span><span>Chat Agents</span></button>
<button class="nav-item" data-panel="memory"><span class="icon">🧠</span><span>Memoire</span></button>
<button class="nav-item" data-panel="skills"><span class="icon">🧩</span><span>Skills</span><span class="badge" id="skills-count">0</span></button>
<button class="nav-item" data-panel="kanban"><span class="icon">📋</span><span>Kanban</span></button>
<button class="nav-item" id="admin-btn" style="display:none" data-panel="admin"><span class="icon">⚙️</span><span>Administration</span></button>
</nav>
<div class="sidebar-footer"><div class="user-info"><div class="avatar">A</div><span id="user-name">{{USER_NAME}}</span></div><a href="/logout">Deconnexion</a></div>
</aside>
<div class="main">
<div class="topbar"><div class="page-title" id="page-title">📊 Dashboard</div>
<div class="stats"><div class="stat"><div class="val" id="stat-agents">0</div><div class="lbl">Agents</div></div><div class="stat"><div class="val" id="stat-calls">0</div><div class="lbl">Requetes</div></div><div class="stat"><div class="val" id="stat-uptime">0</div><div class="lbl">Uptime</div></div></div></div>
<div class="content">

<!-- PANEL: Overview -->
<div class="panel active" id="panel-overview"><div class="grid" id="agents-grid"></div></div>

<!-- PANEL: Canvas -->
<div class="panel" id="panel-canvas">
<div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap">
<span style="font-size:14px;font-weight:600">🖥️ Terminaux des agents</span>
<span style="font-size:11px;color:var(--text3)">Visualisation en temps reel des sessions actives</span>
</div>
<div class="canvas-grid" id="canvas-grid"></div>
</div>

<!-- PANEL: Graph -->
<div class="panel" id="panel-graph">
<div style="display:flex;align-items:center;gap:16px;margin-bottom:16px;flex-wrap:wrap">
<span style="font-size:14px;font-weight:600">🔗 Graphe des taches</span>
<span style="font-size:11px;color:var(--text3)">Visualisation des dependances et de l'avancement</span>
</div>
<div class="graph-container"><svg class="graph-svg" id="graph-svg"><defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="var(--border)"/></marker></defs></svg></div>
</div>

<!-- PANEL: Chat -->
<div class="panel" id="panel-chat">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
<div style="display:flex;gap:12px;flex-wrap:wrap;flex:1" id="chat-tabs"></div>
<button onclick="openCreateAgentModal()" style="background:var(--green);color:#000;border:none;border-radius:6px;padding:8px 14px;font-size:12px;cursor:pointer;font-weight:600;white-space:nowrap">+ Creer un agent</button>
</div>

<!-- Create Agent Modal -->
<div id="create-agent-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:100;justify-content:center;align-items:center">
<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;width:500px;max-width:90vw">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
<span style="font-size:16px;font-weight:600">🤖 Creer un agent IA</span>
<button onclick="document.getElementById('create-agent-modal').style.display='none'" style="background:none;border:none;color:var(--text2);font-size:18px;cursor:pointer">✕</button>
</div>
<div style="margin-bottom:12px"><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Nom unique</label>
<input id="aa-name" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none" placeholder="ex: mon-agent"></div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px">
<div><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Emoji</label>
<input id="aa-emoji" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none" value="🤖"></div>
<div><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Couleur</label>
<input id="aa-color" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none" value="#58a6ff"></div></div>
<div style="margin-bottom:16px"><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Description / Role</label>
<input id="aa-desc" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none" placeholder="Description du role"></div>
<div style="display:flex;gap:8px;align-items:center">
<button onclick="adminCreateAgent()" style="background:var(--green);color:#000;border:none;border-radius:6px;padding:8px 16px;font-size:12px;cursor:pointer;font-weight:600">Creer l'agent</button>
<button onclick="document.getElementById('create-agent-modal').style.display='none'" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:8px 16px;font-size:12px;cursor:pointer">Annuler</button>
<span id="aa-msg" style="font-size:11px;color:var(--text3)"></span>
</div></div></div>

<!-- Delete Agent Modal -->
<div id="delete-agent-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:100;justify-content:center;align-items:center">
<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;width:500px;max-width:90vw">
<div style="display:flex;align-items:center;gap:8px;margin-bottom:16px">
<span style="font-size:18px;color:var(--red)">⚠️</span>
<span style="font-size:16px;font-weight:600">Supprimer l'agent</span>
</div>
<div style="margin-bottom:12px;font-size:13px;color:var(--text2)">
Cette action est irreversible. Tapez <strong id="da-agent-name-confirm" style="color:var(--red)"></strong> pour confirmer la suppression.
</div>
<input id="da-confirm-input" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:10px 12px;color:var(--text);font-size:14px;outline:none;margin-bottom:16px" placeholder="Tapez le nom de l'agent a supprimer">
<div style="display:flex;gap:8px">
<button id="da-confirm-btn" disabled style="background:var(--red);color:#fff;border:none;border-radius:6px;padding:8px 16px;font-size:12px;cursor:pointer;font-weight:600;opacity:0.5">Confirmer la suppression</button>
<button onclick="closeDeleteAgentModal()" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:8px 16px;font-size:12px;cursor:pointer">Annuler</button>
</div></div></div>

<div class="card"><div class="card-header"><div class="card-title" id="chat-agent-name">Selectionne un agent</div>
<button id="chat-delete-agent-btn" style="display:none;margin-left:auto;background:none;border:1px solid var(--border);border-radius:6px;padding:4px 10px;color:var(--red);font-size:11px;cursor:pointer" onclick="openDeleteAgentModal(curAgent)">✕ Supprimer</button>
</div>
<div class="card-body"><div class="chat-log" id="chat-log"><div style="text-align:center;padding:20px;color:var(--text3);font-size:13px">Choisis un agent ci-dessus</div></div>
<div class="chat-input-row"><input type="text" id="chat-input" placeholder="Ecris ton message..." onkeydown="if(event.key==='Enter')sendChat()"><button id="chat-btn" onclick="sendChat()">Envoyer</button></div></div></div></div>

<!-- PANEL: Memory -->
<div class="panel" id="panel-memory"><div id="memory-list"></div></div>

<!-- PANEL: Skills -->
<div class="panel" id="panel-skills"><div class="skills-grid" id="skills-grid"></div></div>

<!-- PANEL: Kanban -->
<div class="panel" id="panel-kanban">
<div style="display:flex;gap:12px;margin-bottom:16px;align-items:center"><button class="nav-item" style="width:auto;padding:8px 16px" onclick="addTask()">+ Ajouter une mission</button></div>
<div class="kanban"><div class="kanban-col"><h3>📋 A faire <span class="count" id="todo-count">0</span></h3><div id="kanban-todo"></div></div>
<div class="kanban-col"><h3>🔄 En cours <span class="count" id="progress-count">0</span></h3><div id="kanban-progress"></div></div>
<div class="kanban-col"><h3>✅ Termine <span class="count" id="done-count">0</span></h3><div id="kanban-done"></div></div></div></div>

<!-- PANEL: Admin -->
<div class="panel" id="panel-admin">
<div style="display:flex;gap:20px;margin-bottom:24px;flex-wrap:wrap" id="admin-stats-bar"></div>

<!-- Create user form -->
<div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:20px;margin-bottom:20px">
<div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
<span style="font-size:16px;font-weight:600">➕ Creer un utilisateur</span>
</div>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px">
<div><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Nom</label>
<input id="au-name" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none" placeholder="Nom"></div>
<div><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Email</label>
<input id="au-email" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none" placeholder="email@local.home"></div>
<div><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Mot de passe</label>
<input id="au-pass" type="password" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none" placeholder="6+ caracteres"></div>
<div><label style="display:block;font-size:11px;color:var(--text2);margin-bottom:4px">Role</label>
<select id="au-role" style="width:100%;background:var(--bg);border:1px solid var(--border);border-radius:6px;padding:8px 10px;color:var(--text);font-size:13px;outline:none;cursor:pointer">
<option value="user">Utilisateur</option><option value="admin">Administrateur</option></select></div>
</div>
<div style="margin-top:12px;display:flex;gap:8px;align-items:center">
<button onclick="adminCreateUser()" style="background:var(--blue);color:#000;border:none;border-radius:6px;padding:8px 16px;font-size:12px;cursor:pointer;font-weight:600">Creer</button>
<span id="au-msg" style="font-size:11px;color:var(--text3)"></span>
</div>
</div>

<!-- Create agent form - REMOVED from admin, moved to chat panel -->


<!-- Permissions modal (hidden by default) -->
<div id="perms-modal" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:100;justify-content:center;align-items:center">
<div style="background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:24px;width:600px;max-width:90vw;max-height:80vh;overflow-y:auto">
<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
<span style="font-size:16px;font-weight:600">🔑 Permissions</span>
<span id="perms-user-name" style="font-size:13px;color:var(--text2)"></span>
<button onclick="document.getElementById('perms-modal').style.display='none'" style="background:none;border:none;color:var(--text2);font-size:18px;cursor:pointer">✕</button>
</div>
<div style="margin-bottom:16px">
<div style="font-size:12px;color:var(--text2);margin-bottom:8px;font-weight:600">Panneaux autorises</div>
<div id="perms-panels" style="display:flex;flex-wrap:wrap;gap:6px"></div>
</div>
<div style="margin-bottom:16px">
<div style="font-size:12px;color:var(--text2);margin-bottom:8px;font-weight:600">Agents autorises</div>
<div id="perms-agents" style="display:flex;flex-wrap:wrap;gap:6px"></div>
</div>
<div style="display:flex;gap:8px">
<button onclick="adminSavePerms()" style="background:var(--blue);color:#000;border:none;border-radius:6px;padding:8px 16px;font-size:12px;cursor:pointer;font-weight:600">Enregistrer</button>
<button onclick="document.getElementById('perms-modal').style.display='none'" style="background:var(--surface2);color:var(--text);border:1px solid var(--border);border-radius:6px;padding:8px 16px;font-size:12px;cursor:pointer">Annuler</button>
</div>
</div></div>

<!-- Users table -->
<table style="width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden">
<thead><tr style="background:var(--surface2)"><th style="padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase">ID</th><th style="padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase">Nom</th><th style="padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase">Email</th><th style="padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase">Role</th><th style="padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase">Permissions</th><th style="padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase">Statut</th><th style="padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase">Actions</th></tr></thead>
<tbody id="admin-users-tbody"></tbody></table></div>

</div></div></div>
<script>
var curAgent=null,agents={},skills=[],tasks=JSON.parse(localStorage.getItem('aos_tasks')||'[]'),chatHist={},canvasHist={};
var role='{{USER_ROLE}}';if(role==='admin')document.getElementById('admin-btn').style.display='flex';

async function loadStatus(){var r=await fetch('/api/status'),d=await r.json();
document.getElementById('stat-agents').textContent=d.profiles.length;
document.getElementById('stat-calls').textContent=d.total_calls;
var h=Math.floor(d.uptime_seconds/3600),m=Math.floor((d.uptime_seconds%3600)/60);
document.getElementById('stat-uptime').textContent=h+'h'+m;}

async function loadProfiles(){var r=await fetch('/api/profiles'),d=await r.json();
agents={};var grid=document.getElementById('agents-grid'),tabs=document.getElementById('chat-tabs'),ml=document.getElementById('memory-list'),cg=document.getElementById('canvas-grid');
grid.innerHTML='';tabs.innerHTML='';ml.innerHTML='';cg.innerHTML='';
d.profiles.forEach(function(p){agents[p.name]=p;
if(!chatHist[p.name])chatHist[p.name]=[];
if(!canvasHist[p.name])canvasHist[p.name]=['> Systeme: Agent '+p.name+' pret'];

// Dashboard card
var card=document.createElement('div');card.className='card';
card.innerHTML='<div class="card-header"><div class="card-avatar" style="background:'+p.color+'22">'+p.emoji+'</div><div><div class="card-title">'+p.name+'</div><div class="card-subtitle">'+p.desc+'</div></div><div style="margin-left:auto"><span class="status-dot online"><span class="pulse"></span> pret</span></div></div><div class="card-body"><div class="chat-log" id="cl-'+p.name+'">'+(chatHist[p.name].length===0?'<span style="color:var(--text3);font-size:11px">Pose une question...</span>':chatHist[p.name].map(function(m){return '<div class="chat-msg '+m.role+'">'+esc(m.content)+'</div>'}).join(''))+'</div><div class="chat-input-row"><input type="text" id="ci-'+p.name+'" placeholder="Message..." onkeydown="if(event.key===\'Enter\')quickChat(\''+p.name+'\')"><button onclick="quickChat(\''+p.name+'\')">Envoyer</button></div></div>';
grid.appendChild(card);

// Canvas terminal
var can=document.createElement('div');can.className='canvas-agent';
var lines=canvasHist[p.name].map(function(l){return '<div class="line '+l.type+'">'+esc(l.text)+'</div>'}).join('');
can.innerHTML='<div class="ca-header" style="border-left:3px solid '+p.color+'"><span>'+p.emoji+'</span><span>'+p.name+'</span><span style="margin-left:auto;font-size:10px;color:var(--text3);font-weight:400">terminal</span></div><div class="ca-log" id="cal-'+p.name+'">'+lines+'</div><div class="ca-input"><input type="text" id="cai-'+p.name+'" placeholder="$ commande..." onkeydown="if(event.key===\'Enter\')canvasCmd(\''+p.name+'\')"><button onclick="canvasCmd(\''+p.name+'\')">exec</button></div>';
cg.appendChild(can);

// Chat tab with delete button
var tab=document.createElement('div');tab.style.display='flex';tab.style.alignItems='center';tab.style.gap='4px';tab.style.background=(curAgent===p.name?'var(--blue)':'var(--surface2)');tab.style.borderRadius='8px';tab.style.padding='4px 4px 4px 12px';tab.style.cursor='pointer';tab.style.fontSize='12px';tab.style.fontWeight='500';tab.style.color=(curAgent===p.name?'#fff':'var(--text)');tab.className='chat-tab-item';
var tabLabel=document.createElement('span');tabLabel.textContent=p.emoji+' '+p.name;tabLabel.style.cursor='pointer';tabLabel.onclick=function(){selectAgent(p.name)};tab.appendChild(tabLabel);
var delBtn=document.createElement('button');delBtn.innerHTML='✕';delBtn.style.background='none';delBtn.style.border='none';delBtn.style.color=(curAgent===p.name?'rgba(255,255,255,0.7)':'var(--text3)');delBtn.style.cursor='pointer';delBtn.style.fontSize='11px';delBtn.style.padding='4px 6px';delBtn.style.borderRadius='4px';delBtn.title='Supprimer '+p.name;
delBtn.onmouseover=function(){delBtn.style.background='rgba(248,81,73,0.3)'};delBtn.onmouseout=function(){delBtn.style.background='none'};
delBtn.onclick=function(event){event.stopPropagation();openDeleteAgentModal(p.name)};tab.appendChild(delBtn);
tabs.appendChild(tab);

// Memory
var mc=document.createElement('div');mc.className='memory-card';
mc.innerHTML='<div class="mem-header" onclick="this.parentElement.classList.toggle(\'open\')"><span style="font-size:20px">'+p.emoji+'</span><span style="font-weight:600;font-size:13px">'+p.name+'</span><span style="margin-left:auto;color:var(--text3);font-size:11px">'+(p.has_memory?'🧠 memoire':'vide')+'</span></div><div class="mem-body"><div class="mem-text">'+(p.memory||'Aucune memoire')+'</div></div>';
ml.appendChild(mc);});
if(!curAgent&&d.profiles.length>0)selectAgent(d.profiles[0].name);
renderGraph();}

async function loadSkills(){var r=await fetch('/api/skills'),d=await r.json();skills=d.skills;
document.getElementById('skills-count').textContent=skills.length;
var grid=document.getElementById('skills-grid');grid.innerHTML='';
skills.forEach(function(s){var c=document.createElement('div');c.className='skill-card';
c.innerHTML='<div class="skill-name">🧩 '+s.name+'</div><div class="skill-path">'+s.path+'</div><div class="skill-desc">'+(s.description||'')+'</div>';grid.appendChild(c);});}

function selectAgent(n){curAgent=n;
document.querySelectorAll('#chat-tabs .nav-item').forEach(function(t){t.classList.remove('active')});
if(event&&event.target)event.target.classList.add('active');
document.getElementById('chat-agent-name').textContent=(agents[n]?agents[n].emoji+' ':'')+n;renderChat();
// Show/hide delete button for non-builtin agents
var builtin=['architect','senior-dev','code-reviewer','qa-engineer','devops','orchestrator'];
var btn=document.getElementById('chat-delete-agent-btn');
if(btn)btn.style.display=(builtin.indexOf(n)>=0||role!=='admin')?'none':'inline-block';}

function renderChat(){var log=document.getElementById('chat-log');
if(!curAgent||!chatHist[curAgent]){log.innerHTML='<div style="text-align:center;padding:20px;color:var(--text3)">Choisis un agent</div>';return;}
var msgs=chatHist[curAgent];
if(msgs.length===0){log.innerHTML='<div style="text-align:center;padding:20px;color:var(--text3)">Demarre une conversation</div>';return;}
log.innerHTML=msgs.map(function(m){return '<div class="chat-msg '+m.role+'">'+esc(m.content)+'</div>'}).join('');log.scrollTop=log.scrollHeight;}

async function sendChat(){var inp=document.getElementById('chat-input'),btn=document.getElementById('chat-btn'),msg=inp.value.trim();if(!msg||!curAgent)return;inp.value='';btn.disabled=true;
chatHist[curAgent].push({role:'user',content:msg});renderChat();
var log=document.getElementById('chat-log');log.innerHTML+='<div class="chat-msg loading" id="chat-loading">...</div>';log.scrollTop=log.scrollHeight;
try{var r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:curAgent,message:msg})});var d=await r.json();
document.getElementById('chat-loading')?.remove();chatHist[curAgent].push({role:'agent',content:d.response});renderChat();}
catch(e){document.getElementById('chat-loading')?.remove();chatHist[curAgent].push({role:'agent',content:'[Erreur] '+e.message});renderChat();}
btn.disabled=false;}

async function quickChat(n){var inp=document.getElementById('ci-'+n),msg=inp.value.trim();if(!msg)return;inp.value='';
chatHist[n]=chatHist[n]||[];chatHist[n].push({role:'user',content:msg});
var log=document.getElementById('cl-'+n);log.innerHTML+='<div class="chat-msg loading">...</div>';
try{var r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:n,message:msg})});var d=await r.json();
log.querySelector('.chat-msg.loading')?.remove();chatHist[n].push({role:'agent',content:d.response});
log.innerHTML=chatHist[n].map(function(m){return '<div class="chat-msg '+m.role+'">'+esc(m.content)+'</div>'}).join('');log.scrollTop=log.scrollHeight;}
catch(e){log.querySelector('.chat-msg.loading')?.remove();chatHist[n].push({role:'agent',content:'[Erreur] '+e.message});}
loadStatus();}

// Canvas: send command to agent terminal
async function canvasCmd(n){var inp=document.getElementById('cai-'+n),msg=inp.value.trim();if(!msg)return;inp.value='';
canvasHist[n]=canvasHist[n]||[];
canvasHist[n].push({type:'cmd',text:'$ '+msg});
var log=document.getElementById('cal-'+n);log.innerHTML+='<div class="line loading" id="caload-'+n+'">⏳ execution...</div>';log.scrollTop=log.scrollHeight;
try{var r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({profile:n,message:msg})});var d=await r.json();
document.getElementById('caload-'+n)?.remove();
canvasHist[n].push({type:'agent',text:d.response});
canvasHist[n].push({type:'done',text:'✔ tâche terminee'});
log.innerHTML=canvasHist[n].map(function(l){return '<div class="line '+l.type+'">'+esc(l.text)+'</div>'}).join('');log.scrollTop=log.scrollHeight;}
catch(e){document.getElementById('caload-'+n)?.remove();canvasHist[n].push({type:'error',text:'[Erreur] '+e.message});}
renderGraph();}

// Graph: visualize tasks and agent flow
function renderGraph(){var svg=document.getElementById('graph-svg');
var agents_list=Object.keys(agents);if(agents_list.length===0){svg.innerHTML='';return;}
var w=svg.clientWidth||800,h=400;
var cols=agents_list.length,colW=Math.max(120,w/(cols+1));
var tasks_all=tasks||[];
var todo=tasks_all.filter(function(t){return t.status==='todo'}).length;
var progress=tasks_all.filter(function(t){return t.status==='progress'}).length;
var done=tasks_all.filter(function(t){return t.status==='done'}).length;

var html='<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 Z" fill="var(--border)"/></marker></defs>';
html+='<rect x="0" y="0" width="'+w+'" height="'+h+'" fill="transparent"/>';

// Background grid
for(var i=0;i<cols;i++){var x=colW*(i+1);
html+='<line x1="'+x+'" y1="40" x2="'+x+'" y2="'+(h-30)+'" stroke="var(--border)" stroke-width="1" stroke-dasharray="4,4" opacity="0.3"/>';}

// Draw agents as nodes
for(var i=0;i<agents_list.length;i++){var name=agents_list[i],info=agents[name]||{};
var x=colW*(i+1),y=80;
var agentTasks=tasks_all.filter(function(t){return t.agent===name});
var aTodo=agentTasks.filter(function(t){return t.status==='todo'}).length;
var aProg=agentTasks.filter(function(t){return t.status==='progress'}).length;
var aDone=agentTasks.filter(function(t){return t.status==='done'}).length;

html+='<g transform="translate('+(x-50)+','+(y-25)+')"><rect x="0" y="0" width="100" height="50" rx="8" fill="var(--surface2)" stroke="'+info.color+'" stroke-width="2" class="graph-node';
if(aDone>0)html+=' done';
html+='"/>';
html+='<text x="50" y="22" class="graph-label" fill="var(--text)">'+info.emoji+' '+name+'</text>';
html+='<text x="50" y="38" class="graph-label sub" fill="var(--text3)">📋'+aTodo+' 🔄'+aProg+' ✅'+aDone+'</text></g>';}

// Draw stats summary at bottom
var statsY=h-20;
html+='<g transform="translate('+(w/2-100)+','+(statsY-15)+')">';
html+='<rect x="0" y="0" width="200" height="30" rx="6" fill="var(--surface)" stroke="var(--border)"/>';
html+='<text x="30" y="20" class="graph-label sub" fill="var(--text3)">📋'+todo+'</text>';
html+='<text x="80" y="20" class="graph-label sub" fill="var(--orange)">🔄'+progress+'</text>';
html+='<text x="130" y="20" class="graph-label sub" fill="var(--green)">✅'+done+'</text>';
html+='<text x="175" y="20" class="graph-label sub" fill="var(--text)">📊'+tasks_all.length+'</text></g>';

svg.innerHTML=html;}

function addTask(){var t=prompt('Titre de la mission :');if(!t)return;
var a=prompt('Agent responsable (architect,senior-dev,code-reviewer,qa-engineer,devops) :');
tasks.push({id:Date.now(),title:t,agent:a||'devops',status:'todo',created:new Date().toISOString()});saveTasks();}
function moveTask(id,s){var t=tasks.find(function(x){return x.id===id});if(t){t.status=s;saveTasks();}}
function deleteTask(id){tasks=tasks.filter(function(t){return t.id!==id});saveTasks();}
function saveTasks(){localStorage.setItem('aos_tasks',JSON.stringify(tasks));renderKanban();renderGraph();}
function renderKanban(){var todo=tasks.filter(function(t){return t.status==='todo'}),prog=tasks.filter(function(t){return t.status==='progress'}),done=tasks.filter(function(t){return t.status==='done'});
document.getElementById('todo-count').textContent=todo.length;document.getElementById('progress-count').textContent=prog.length;document.getElementById('done-count').textContent=done.length;
document.getElementById('kanban-todo').innerHTML=(todo.length?todo.map(function(t){return '<div class="kanban-item" ondblclick="moveTask('+t.id+',\'progress\')"><div class="ki-agent">'+(t.agent||'devops')+'</div><div class="ki-title">'+esc(t.title)+'</div><div class="ki-meta">'+new Date(t.created).toLocaleDateString()+' <span style="float:right;cursor:pointer;color:var(--red)" onclick="event.stopPropagation();deleteTask('+t.id+')">✕</span></div></div>'}).join(''):'<div style="color:var(--text3);font-size:11px">Aucune tache</div>');
document.getElementById('kanban-progress').innerHTML=(prog.length?prog.map(function(t){return '<div class="kanban-item" ondblclick="moveTask('+t.id+',\'done\')"><div class="ki-agent">'+(t.agent||'devops')+'</div><div class="ki-title">'+esc(t.title)+'</div><div class="ki-meta">'+new Date(t.created).toLocaleDateString()+' <span style="float:right;cursor:pointer;color:var(--red)" onclick="event.stopPropagation();deleteTask('+t.id+')">✕</span></div></div>'}).join(''):'<div style="color:var(--text3);font-size:11px">Aucune tache</div>');
document.getElementById('kanban-done').innerHTML=(done.length?done.map(function(t){return '<div class="kanban-item"><div class="ki-agent">'+(t.agent||'devops')+'</div><div class="ki-title" style="text-decoration:line-through;color:var(--text3)">'+esc(t.title)+'</div><div class="ki-meta">'+new Date(t.created).toLocaleDateString()+' <span style="float:right;cursor:pointer;color:var(--red)" onclick="event.stopPropagation();deleteTask('+t.id+')">✕</span></div></div>'}).join(''):'<div style="color:var(--text3);font-size:11px">Aucune tache</div>');}

// Navigation
document.querySelectorAll('.nav-item[data-panel]').forEach(function(i){i.addEventListener('click',function(){document.querySelectorAll('.nav-item').forEach(function(n){n.classList.remove('active')});i.classList.add('active');document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active')});document.getElementById('panel-'+i.dataset.panel).classList.add('active');document.querySelector('.page-title').textContent=i.textContent.trim()})});

function esc(t){var d=document.createElement('div');d.textContent=t;return d.innerHTML;}

// Init
loadStatus();loadProfiles();loadSkills();renderKanban();loadAdmin();setInterval(loadStatus,10000);
// Hide unauthorized panels for non-admin users
if(role!=='admin'){setTimeout(function(){
fetch('/api/status').then(function(r){return r.json()}).then(function(d){
var perms=d.user.permissions||{};
var allowed=perms.panels||[];
document.querySelectorAll('.nav-item[data-panel]').forEach(function(n){
var panel=n.getAttribute('data-panel');
if(panel!=='overview'&&allowed.indexOf(panel)<0){n.style.display='none';}
if(panel==='admin')n.style.display='none';});});},500);}

// Admin panel
async function loadAdmin(){if(role!=='admin')return;
var r=await fetch('/api/users'),d=await r.json();
var panels=d.panels||[],agentsList=d.agents||[];
var tb=document.getElementById('admin-users-tbody');if(!tb)return;tb.innerHTML='';
var admins=d.users.filter(function(u){return u.role==='admin'}).length,users=d.users.filter(function(u){return u.role==='user'}).length,total=d.users.length;
var sb=document.getElementById('admin-stats-bar');
sb.innerHTML='<div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 24px;text-align:center;flex:1;min-width:120px"><div style="font-size:24px;font-weight:700;color:var(--blue)">'+total+'</div><div style="font-size:11px;color:var(--text2);text-transform:uppercase;margin-top:4px">Total</div></div><div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 24px;text-align:center;flex:1;min-width:120px"><div style="font-size:24px;font-weight:700;color:var(--blue)">'+admins+'</div><div style="font-size:11px;color:var(--text2);text-transform:uppercase;margin-top:4px">Administrateurs</div></div><div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 24px;text-align:center;flex:1;min-width:120px"><div style="font-size:24px;font-weight:700;color:var(--blue)">'+users+'</div><div style="font-size:11px;color:var(--text2);text-transform:uppercase;margin-top:4px">Utilisateurs</div></div>';
d.users.forEach(function(u){
var tr=document.createElement('tr');tr.style.borderBottom='1px solid var(--border)';
var rb='<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:'+(u.role==='admin'?'rgba(88,166,255,0.15);color:var(--blue)':'rgba(139,148,158,0.15);color:var(--text2)')+'">'+u.role+'</span>';
var sb2=u.disabled?'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:rgba(248,81,73,0.15);color:var(--red)">desactive</span>':'<span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;background:rgba(63,185,80,0.15);color:var(--green)">actif</span>';
var perms=u.permissions||{};
var permSummary=(u.role==='admin')?'<span style="color:var(--blue);font-size:10px">Tout</span>':'<span style="color:var(--text2);font-size:10px;cursor:pointer" onclick="openPerms('+u.id+',\''+esc(u.name)+'\')">'+(perms.panels?perms.panels.length+' panneaux, ':'0 panneaux, ')+(perms.agents?perms.agents.length+' agents':'0 agents')+' ✏️</span>';
var acts='<select style="padding:4px 8px;border-radius:4px;background:var(--bg);border:1px solid var(--border);color:var(--text);font-size:12px;cursor:pointer" onchange="adminAction('+u.id+',this.value)"><option value="">Action...</option><option value="admin">Promouvoir admin</option><option value="user">Retrograder user</option><option value="'+(u.disabled?'enable':'disable')+'">'+(u.disabled?'Activer':'Desactiver')+'</option><option value="delete">Supprimer</option></select>';
tr.innerHTML='<td style="padding:12px 16px;font-size:13px">'+u.id+'</td><td style="padding:12px 16px;font-size:13px">'+esc(u.name)+'</td><td style="padding:12px 16px;font-size:13px">'+esc(u.email)+'</td><td style="padding:12px 16px;font-size:13px">'+rb+'</td><td style="padding:12px 16px;font-size:13px">'+permSummary+'</td><td style="padding:12px 16px;font-size:13px">'+sb2+'</td><td style="padding:12px 16px;font-size:13px">'+acts+'</td>';
tb.appendChild(tr);});
// Store for permissions modal
window._usersData=d;}
async function adminCreateAgent(){var n=document.getElementById('aa-name').value,e=document.getElementById('aa-emoji').value,c=document.getElementById('aa-color').value,d=document.getElementById('aa-desc').value,msg=document.getElementById('aa-msg');
if(!n){msg.textContent='Le nom est obligatoire';return;}
var resp=await fetch('/api/admin/agent/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,emoji:e,color:c,description:d})});
var r=await resp.json();
if(r.error){msg.textContent=r.error;return;}
msg.textContent='Agent cree !';
document.getElementById('aa-name').value='';document.getElementById('aa-emoji').value='🤖';document.getElementById('aa-color').value='#58a6ff';document.getElementById('aa-desc').value='';
document.getElementById('create-agent-modal').style.display='none';
loadProfiles();loadAdmin();}
function openCreateAgentModal(){document.getElementById('aa-msg').textContent='';document.getElementById('create-agent-modal').style.display='flex';}
var _deleteAgentName=null;
function openDeleteAgentModal(name){_deleteAgentName=name;
document.getElementById('da-agent-name-confirm').textContent=name;
document.getElementById('da-confirm-input').value='';
document.getElementById('da-confirm-btn').disabled=true;
document.getElementById('da-confirm-btn').style.opacity='0.5';
document.getElementById('delete-agent-modal').style.display='flex';}
function closeDeleteAgentModal(){document.getElementById('delete-agent-modal').style.display='none';_deleteAgentName=null;}
document.getElementById('da-confirm-input')?.addEventListener('input',function(){
var match=this.value.trim()===_deleteAgentName;
document.getElementById('da-confirm-btn').disabled=!match;
document.getElementById('da-confirm-btn').style.opacity=match?'1':'0.5';});
async function confirmDeleteAgent(){if(!_deleteAgentName)return;
var resp=await fetch('/api/admin/agent/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:_deleteAgentName})});
var r=await resp.json();
if(r.error){alert('Erreur: '+r.error);return;}
closeDeleteAgentModal();loadProfiles();loadAdmin();}
// Wire delete confirm button
setTimeout(function(){var btn=document.getElementById('da-confirm-btn');if(btn)btn.onclick=confirmDeleteAgent;},100);
async function adminCreateUser(){var n=document.getElementById('au-name').value,e=document.getElementById('au-email').value,p=document.getElementById('au-pass').value,r=document.getElementById('au-role').value,msg=document.getElementById('au-msg');
if(!n||!e||!p){msg.textContent='Remplis tous les champs';return;}
var resp=await fetch('/api/admin/user/create',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n,email:e,password:p,role:r})});
var d=await resp.json();
if(d.error){msg.textContent=d.error;return;}
msg.textContent='Utilisateur cree !';document.getElementById('au-name').value='';document.getElementById('au-email').value='';document.getElementById('au-pass').value='';
loadAdmin();}
var _permsUserId=null;
function openPerms(id,name){_permsUserId=id;
document.getElementById('perms-user-name').textContent=name;
document.getElementById('perms-modal').style.display='flex';
var panels=window._usersData?.panels||['overview','canvas','graph','chat','memory','skills','kanban'];
var agents=window._usersData?.agents||[];
var user=(window._usersData?.users||[]).find(function(u){return u.id===id});
var perms=user?.permissions||{};
var pp=document.getElementById('perms-panels');pp.innerHTML='';
panels.forEach(function(p){var checked=(perms.panels||[]).indexOf(p)>=0;
pp.innerHTML+='<label style="display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:6px;background:var(--surface2);border:1px solid var(--border);cursor:pointer;font-size:11px"><input type="checkbox" '+(checked?'checked':'')+' value="'+p+'" onchange="togglePermPanel(\''+p+'\')"> '+p+'</label>';});
var pa=document.getElementById('perms-agents');pa.innerHTML='';
agents.forEach(function(a){var checked=(perms.agents||[]).indexOf(a)>=0;
pa.innerHTML+='<label style="display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:6px;background:var(--surface2);border:1px solid var(--border);cursor:pointer;font-size:11px"><input type="checkbox" '+(checked?'checked':'')+' value="'+a+'" onchange="togglePermAgent(\''+a+'\')"> '+a+'</label>';});
window._currentPerms=JSON.parse(JSON.stringify(perms));}
function togglePermPanel(p){if(!window._currentPerms.panels)window._currentPerms.panels=[];
var idx=window._currentPerms.panels.indexOf(p);
if(idx>=0)window._currentPerms.panels.splice(idx,1);else window._currentPerms.panels.push(p);}
function togglePermAgent(a){if(!window._currentPerms.agents)window._currentPerms.agents=[];
var idx=window._currentPerms.agents.indexOf(a);
if(idx>=0)window._currentPerms.agents.splice(idx,1);else window._currentPerms.agents.push(a);}
async function adminSavePerms(){if(!_permsUserId)return;
await fetch('/api/admin/user/permissions',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:_permsUserId,permissions:window._currentPerms})});
document.getElementById('perms-modal').style.display='none';loadAdmin();}
async function adminAction(id,action){if(!action)return;
if(action==='delete'){if(!confirm('Supprimer cet utilisateur ?'))return;
await fetch('/api/admin/user/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});}
else if(action==='enable'){await fetch('/api/admin/user/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,disabled:false})});}
else if(action==='disable'){await fetch('/api/admin/user/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,disabled:true})});}
else{await fetch('/api/admin/user/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,role:action})});}
loadAdmin();}
</script>
</body></html>"""


ADMIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Agentic OS â€” Administration</title>
<style>
:root{--bg:#0d1117;--surface:#161b22;--surface2:#1c2333;--border:#30363d;--text:#c9d1d9;--text2:#8b949e;--text3:#484f58;--blue:#58a6ff;--green:#3fb950;--red:#f85149}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
::-webkit-scrollbar{width:6px}
::-webkit-scrollbar-track{background:var(--bg)}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
.app{display:flex;min-height:100vh}
.sidebar{width:240px;min-width:240px;background:var(--surface);border-right:1px solid var(--border);display:flex;flex-direction:column;position:sticky;top:0;height:100vh}
.sidebar-logo{padding:20px 20px 16px;border-bottom:1px solid var(--border)}
.sidebar-logo h1{font-size:18px;font-weight:700;color:var(--blue);display:flex;align-items:center;gap:8px}
.sidebar-logo .ver{font-size:10px;color:var(--text3);margin-top:2px}
.sidebar-nav{padding:12px 10px;flex:1}
.nav-item{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:8px;cursor:pointer;color:var(--text2);font-size:13px;font-weight:500;margin-bottom:2px;border:none;background:none;width:100%;text-align:left;transition:all 0.15s;text-decoration:none}
.nav-item:hover{background:var(--surface2);color:var(--text)}
.nav-item.active{background:var(--blue);color:#fff}
.nav-item .icon{font-size:17px;width:22px;text-align:center}
.sidebar-footer{padding:12px 20px;border-top:1px solid var(--border);font-size:11px;color:var(--text3)}
.sidebar-footer .user-info{display:flex;align-items:center;gap:8px;margin-bottom:8px}
.sidebar-footer .user-info .avatar{width:28px;height:28px;border-radius:50%;background:var(--blue);display:flex;align-items:center;justify-content:center;font-size:12px;color:#000;font-weight:700}
.sidebar-footer a{color:var(--text2);text-decoration:none;display:block;padding:4px 0}
.sidebar-footer a:hover{color:var(--text)}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden}
.topbar{background:var(--surface);border-bottom:1px solid var(--border);padding:12px 24px;display:flex;align-items:center;gap:20px;flex-wrap:wrap}
.topbar .page-title{font-size:15px;font-weight:600}
.content{flex:1;overflow-y:auto;padding:24px}
.stats-bar{display:flex;gap:20px;margin-bottom:24px;flex-wrap:wrap}
.stats-bar .s{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:16px 24px;text-align:center;flex:1;min-width:120px}
.stats-bar .s .v{font-size:24px;font-weight:700;color:var(--blue)}
.stats-bar .s .l{font-size:11px;color:var(--text2);text-transform:uppercase;margin-top:4px}
table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden}
th{background:var(--surface2);padding:12px 16px;text-align:left;font-size:11px;color:var(--text2);text-transform:uppercase;letter-spacing:0.5px;border-bottom:1px solid var(--border)}
td{padding:12px 16px;font-size:13px;border-bottom:1px solid var(--border)}
tr:last-child td{border-bottom:none}
tr:hover td{background:var(--surface2)}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}
.badge.admin{background:rgba(88,166,255,0.15);color:var(--blue)}
.badge.user{background:rgba(139,148,158,0.15);color:var(--text2)}
.badge.disabled{background:rgba(248,81,73,0.15);color:var(--red)}
select{padding:4px 8px;border-radius:4px;background:var(--bg);border:1px solid var(--border);color:var(--text);font-size:12px;cursor:pointer}
.btn{padding:6px 12px;border-radius:6px;border:1px solid var(--border);background:var(--surface2);color:var(--text);font-size:11px;cursor:pointer;font-family:inherit}
.btn:hover{border-color:var(--blue)}
@media(max-width:768px){.sidebar{width:60px;min-width:60px}.sidebar-logo h1 span,.nav-item span:not(.icon),.sidebar-footer .user-info span,.sidebar-footer a span{display:none}}
</style></head>
<body>
<div class="app">
<aside class="sidebar">
<div class="sidebar-logo"><h1>\u26A1<span> Agentic OS</span></h1><div class="ver">v2.0</div></div>
<nav class="sidebar-nav">
<button class="nav-item" onclick="location.href='/dashboard'"><span class="icon">📊</span><span>Dashboard</span></button>
<button class="nav-item" onclick="location.href='/dashboard'"><span class="icon">💬</span><span>Chat Agents</span></button>
<button class="nav-item" onclick="location.href='/dashboard'"><span class="icon">🧠</span><span>Memoire</span></button>
<button class="nav-item" onclick="location.href='/dashboard'"><span class="icon">🧩</span><span>Skills</span></button>
<button class="nav-item" onclick="location.href='/dashboard'"><span class="icon">📋</span><span>Kanban</span></button>
<button class="nav-item active" onclick="location.href='/admin'"><span class="icon">⚙️</span><span>Administration</span></button>
</nav>
<div class="sidebar-footer">
<div class="user-info"><div class="avatar">A</div><span id="user-name">{{USER_NAME}}</span></div>
<a href="/logout"><span>Deconnexion</span></a>
</div>
</aside>
<div class="main">
<div class="topbar"><div class="page-title">âš™ï¸ Administration</div></div>
<div class="content">
<div class="stats-bar" id="stats-bar"></div>
<table><thead><tr><th>ID</th><th>Nom</th><th>Email</th><th>Role</th><th>Statut</th><th>Date</th><th>Actions</th></tr></thead>
<tbody id="users-tbody"></tbody></table>
</div></div></div>
<script>
async function loadUsers(){const r=await fetch('/api/users');const d=await r.json();
const tb=document.getElementById('users-tbody');tb.innerHTML='';
const admins=d.users.filter(u=>u.role==='admin').length,users=d.users.filter(u=>u.role==='user').length,total=d.users.length;
document.getElementById('stats-bar').innerHTML='<div class="s"><div class="v">'+total+'</div><div class="l">Total</div></div><div class="s"><div class="v">'+admins+'</div><div class="l">Administrateurs</div></div><div class="s"><div class="v">'+users+'</div><div class="l">Utilisateurs</div></div>';
d.users.forEach(u=>{
const tr=document.createElement('tr');
const roleBadge='<span class="badge '+(u.role==='admin'?'admin':'user')+'">'+u.role+'</span>';
const statusBadge=u.disabled?'<span class="badge disabled">desactive</span>':'<span class="badge" style="background:rgba(63,185,80,0.15);color:var(--green)">actif</span>';
const actions='<select onchange="updateUser('+u.id+',this.value)"><option value="">Action...</option><option value="admin">Promouvoir admin</option><option value="user">Retrogader user</option><option value="'+(u.disabled?'enable':'disable')+'">'+(u.disabled?'Activer':'Desactiver')+'</option><option value="delete">Supprimer</option></select>';
tr.innerHTML='<td>'+u.id+'</td><td>'+esc(u.name)+'</td><td>'+esc(u.email)+'</td><td>'+roleBadge+'</td><td>'+statusBadge+'</td><td>'+u.created_at+'</td><td>'+actions+'</td>';
tb.appendChild(tr);});}
async function updateUser(id,action){if(!action)return;
if(action==='delete'){if(!confirm('Supprimer cet utilisateur ?'))return;
await fetch('/api/admin/user/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id})});}
else if(action==='enable'){await fetch('/api/admin/user/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,disabled:false})});}
else if(action==='disable'){await fetch('/api/admin/user/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,disabled:true})});}
else{await fetch('/api/admin/user/update',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id,role:action})});}
loadUsers();}
function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML;}
loadUsers();
</script>
</body></html>"""


def main():
    server = HTTPServer((HOST, PORT), AgenticOSHandler)
    print(f"[Agentic OS] Dashboard + Auth en ecoute sur http://{HOST}:{PORT}")
    print(f"[Agentic OS] Base de donnees: {DB_PATH}")
    print(f"[Agentic OS] API OpenAI-compatible: http://{HOST}:{PORT}/v1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Agentic OS] Arret.")
        server.server_close()


if __name__ == "__main__":
    main()
