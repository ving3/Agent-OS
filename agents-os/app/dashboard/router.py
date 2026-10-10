# -*- coding: utf-8 -*-
"""
Agentic OS — Routeur du dashboard : gere les requetes HTTP (auth, pages, API)
"""
import json
import html as html_mod
import time
import subprocess
from urllib.parse import urlparse, parse_qs

from config import HOST, PORT, DATA_DIR, PANELS, AGENTS
from database import (
    get_db, get_user_count, get_user_by_id, generate_token, hash_password,
    check_panel_access, check_agent_access, get_user_from_token
)
from hermes_client import (
    call_hermes_api, get_agent_memory, list_skills, list_profiles,
    stats, stats_lock, http_client
)
from common.http_base import AgenticOSBaseHandler
from common.templates import LOGIN_PAGE, SIGNUP_PAGE
from dashboard.templates import DASHBOARD_HTML, ADMIN_HTML


class AgenticOSHandler(AgenticOSBaseHandler):
    """Gestionnaire HTTP principal : aiguille les requetes vers les bons handlers."""

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
                self._send_html(self._render_admin(user))
            return

        if path.startswith("/admin/user/"):
            admin = self._require_admin()
            if not admin:
                return
            uid = path.split("/")[-1]
            conn = get_db()
            row = conn.execute("SELECT id, name, email, role, disabled, created_at FROM users WHERE id = ?",
                               (uid,)).fetchone()
            conn.close()
            if row:
                self._send_json({"id": row[0], "name": row[1], "email": row[2], "role": row[3],
                                 "disabled": bool(row[4]), "created_at": row[5]})
            else:
                self._send_json({"error": "User not found"}, 404)
            return

        # --- API endpoints ---
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
            rows = conn.execute(
                "SELECT id, name, email, role, disabled, created_at, permissions FROM users ORDER BY id"
            ).fetchall()
            conn.close()
            users = [{"id": r[0], "name": r[1], "email": r[2], "role": r[3], "disabled": bool(r[4]),
                       "created_at": r[5], "permissions": json.loads(r[6]) if r[6] else {}} for r in rows]
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
            row = conn.execute("SELECT id, name, email, role, disabled FROM users WHERE email = ?",
                               (email,)).fetchone()
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
            if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
                conn.close()
                self._send_json({"error": "Cet email est deja utilise"}, 409)
                return
            if conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone():
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
            if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
                conn.close()
                self._send_json({"error": "Cet email est deja utilise"}, 409)
                return
            if conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone():
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
            conn.execute("UPDATE users SET permissions = ? WHERE id = ?", (json.dumps(permissions), uid))
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
            existing = list_profiles()
            if len(existing) >= 50:
                self._send_json({"error": "Maximum 50 agents atteint"}, 400)
                return
            if name in existing:
                self._send_json({"error": f"L'agent '{name}' existe deja"}, 409)
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
                    self._send_json({"error": f"Erreur creation: {result.stderr.strip()}"}, 500)
                    return
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
            builtin = {"architect", "senior-dev", "code-reviewer", "qa-engineer", "devops", "orchestrator"}
            if name in builtin:
                self._send_json({"error": "Impossible de supprimer un agent integre"}, 400)
                return
            try:
                result = subprocess.run(
                    ["kubectl", "exec", "-n", "ai", "deployment/hermes", "--",
                     "rm", "-rf", f"/opt/data/profiles/{name}"],
                    capture_output=True, text=True, timeout=15,
                )
                if result.returncode != 0:
                    self._send_json({"error": f"Erreur suppression: {result.stderr.strip()}"}, 500)
                    return
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

    def _render_dashboard(self, user: dict, panel: str = "overview") -> str:
        html = DASHBOARD_HTML.replace("{{USER_NAME}}", html_mod.escape(user["name"])) \
            .replace("{{USER_ROLE}}", html_mod.escape(user["role"])) \
            .replace("{{USER_EMAIL}}", html_mod.escape(user["email"]))
        html = html.replace('data-panel="overview" class="nav-item active"', 'data-panel="overview" class="nav-item"')
        html = html.replace(f'data-panel="{panel}" class="nav-item"', f'data-panel="{panel}" class="nav-item active"')
        html = html.replace('class="panel active" id="panel-overview"', 'class="panel" id="panel-overview"')
        html = html.replace(f'class="panel" id="panel-{panel}"', f'class="panel active" id="panel-{panel}"')
        return html

    def _render_admin(self, user: dict) -> str:
        return ADMIN_HTML.replace("{{USER_NAME}}", html_mod.escape(user["name"]))
