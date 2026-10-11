# -*- coding: utf-8 -*-
"""Agent OS — Configuration centralisee"""
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")
HERMES_API_URL = os.environ.get("HERMES_API_URL", "http://hermes:8777")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
PROFILES_DIR = os.environ.get("PROFILES_DIR", "/opt/data/profiles")
SKILLS_DIR = os.environ.get("SKILLS_DIR", "/opt/data/skills")

HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("BRIDGE_PORT", "8686"))

DB_PATH = os.path.join(DATA_DIR, "agentic_os.db")
STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "dist")

PANELS = ["overview", "canvas", "graph", "chat", "memory", "skills", "kanban", "admin"]

AGENTS: dict[str, dict] = {
    "architect":   {"emoji": "🏛️", "color": "#1f6feb", "desc": "Conception système, ADR, choix technologiques"},
    "senior-dev":  {"emoji": "💻", "color": "#238636", "desc": "Implémentation full-stack, APIs, debugging"},
    "code-reviewer": {"emoji": "🔍", "color": "#8957e5", "desc": "Audit sécurité, qualité, bonnes pratiques"},
    "qa-engineer": {"emoji": "🧪", "color": "#d29922", "desc": "Tests, TDD, chasse aux bugs"},
    "devops":      {"emoji": "⚙️",  "color": "#da3633", "desc": "CI/CD, conteneurs, infrastructure"},
}
