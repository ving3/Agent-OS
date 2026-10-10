# -*- coding: utf-8 -*-
"""
Agentic OS — Configuration centralisee
"""
import os

# --- Chemins ---
DATA_DIR = os.environ.get("DATA_DIR", "/data")
HERMES_API_URL = os.environ.get("HERMES_API_URL", "http://hermes:8777")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
PROFILES_DIR = os.environ.get("PROFILES_DIR", "/opt/data/profiles")
SKILLS_DIR = os.environ.get("SKILLS_DIR", "/opt/data/skills")

# --- Serveur ---
HOST = os.environ.get("BRIDGE_HOST", "0.0.0.0")
PORT = int(os.environ.get("BRIDGE_PORT", "8686"))

# --- Base de donnees ---
DB_PATH = os.path.join(DATA_DIR, "agentic_os.db")

# --- Panneaux du dashboard ---
PANELS = ["overview", "canvas", "graph", "chat", "memory", "skills", "kanban", "admin"]

# --- Agents disponibles ---
AGENTS = {
    "architect": {"emoji": "\U0001F3DB\uFE0F", "color": "#1f6feb", "desc": "Conception systeme, ADR, choix technologiques"},
    "senior-dev": {"emoji": "\U0001F4BB", "color": "#238636", "desc": "Implementation full-stack, APIs, debugging"},
    "code-reviewer": {"emoji": "\U0001F50D", "color": "#8957e5", "desc": "Audit securite, qualite, bonnes pratiques"},
    "qa-engineer": {"emoji": "\U0001F9EA", "color": "#d29922", "desc": "Tests, TDD, chasse aux bugs"},
    "devops": {"emoji": "\u2699\uFE0F", "color": "#da3633", "desc": "CI/CD, conteneurs, infrastructure"},
}
