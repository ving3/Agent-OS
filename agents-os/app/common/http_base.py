# -*- coding: utf-8 -*-
"""
Agentic OS — Base HTTP handler : envoi reponses et helpers d'auth
"""
import json
from http.server import BaseHTTPRequestHandler
from database import get_user_from_token


class AgenticOSBaseHandler(BaseHTTPRequestHandler):
    """Classe de base avec les methodes de reponse et d'authentification."""

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

    def _redirect(self, location: str):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

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
            self._send_html("<h1>401 Non autorise</h1><p>Connectez-vous d'abord.</p>", 401)
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
