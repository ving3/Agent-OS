# -*- coding: utf-8 -*-
"""
Agentic OS — Routeur du dashboard : aiguille les requetes HTTP
vers les handlers des panneaux correspondants.
"""
import html as html_mod
from urllib.parse import urlparse, parse_qs

from config import HOST, PORT, DATA_DIR, PANELS, AGENTS
from database import get_db, generate_token, hash_password
from common.http_base import AgenticOSBaseHandler
from common.templates import LOGIN_PAGE, SIGNUP_PAGE
from dashboard.templates import DASHBOARD_HTML, ADMIN_HTML

from panels import overview, skills, chat
from panels import admin as admin_panel


class AgenticOSHandler(AgenticOSBaseHandler):
    """Gestionnaire HTTP : aiguille les requetes vers les handlers des panneaux."""

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
            if self._get_user():
                self._send_html(self._render_admin(user))
            return

        # --- Delegation aux panneaux ---

        # Overview
        if path == "/api/status":
            overview.handle_status(self, user)
            return
        if path == "/api/profiles":
            overview.handle_profiles(self, user)
            return
        if path.startswith("/api/profile/"):
            overview.handle_profile(self, path.split("/")[-1])
            return
        if path == "/v1/models":
            overview.handle_models(self)
            return

        # Skills
        if path == "/api/skills":
            skills.handle_skills(self)
            return

        # Admin
        if path == "/api/users":
            admin_panel.handle_list_users(self)
            return
        if path.startswith("/admin/user/"):
            admin_panel.handle_get_user(self, path.split("/")[-1])
            return

        self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        body = self._read_body()

        # --- Auth ---
        if path == "/api/login":
            self._handle_login(body)
            return

        if path == "/api/signup":
            self._handle_signup(body)
            return

        # --- Delegation aux panneaux ---

        # Admin
        if path == "/api/admin/user/create":
            admin_panel.handle_create_user(self, body)
            return
        if path == "/api/admin/user/permissions":
            admin_panel.handle_update_user_permissions(self, body)
            return
        if path == "/api/admin/user/update":
            admin_panel.handle_update_user(self, body)
            return
        if path == "/api/admin/user/delete":
            admin_user = self._require_admin()
            if admin_user:
                admin_panel.handle_delete_user(self, body, admin_user)
            return
        if path == "/api/admin/agent/create":
            admin_panel.handle_create_agent(self, body)
            return
        if path == "/api/admin/agent/delete":
            admin_panel.handle_delete_agent(self, body)
            return

        # Chat
        if path == "/v1/chat/completions":
            chat.handle_chat_completions(self, body)
            return
        if path == "/api/chat":
            chat.handle_chat(self, body)
            return

        self._send_json({"error": "Not found"}, 404)

    # --- Handlers d'auth (internes au routeur) ---

    def _handle_login(self, body):
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

    def _handle_signup(self, body):
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

    # --- Rendu des pages ---

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
