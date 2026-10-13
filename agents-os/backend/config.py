# -*- coding: utf-8 -*-
"""Agent OS — Configuration centralisee"""
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")
HERMES_API_URL = os.environ.get("HERMES_API_URL", "http://hermes:8777")
HERMES_API_KEY = os.environ.get("HERMES_API_KEY", "")
PROFILES_DIR = os.environ.get("PROFILES_DIR", "/opt/data/profiles")
SKILLS_DIR = os.environ.get("SKILLS_DIR", "/opt/data/skills")
N8N_URL = os.environ.get("N8N_URL", "http://n8n:5678")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")

# Ownership des fichiers profils cote Hermes (hermes-agent tourne en uid/gid 10000)
HERMES_UID = int(os.environ.get("HERMES_UID", "10000"))
HERMES_GID = int(os.environ.get("HERMES_GID", "10000"))

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

# ── Fournisseurs LLM disponibles pour la creation d'agents ────────────────────
# key_env : variable d'environnement contenant la cle API du fournisseur.
# Si la variable n'est pas definie, Hermes utilise la cle globale (OPENAI_API_KEY).
PROVIDERS: dict[str, dict] = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-v4-pro", "deepseek-flash"],
        "key_env": "DEEPSEEK_API_KEY",
    },
    "byteplus": {
        "label": "BytePlus ARK (legacy)",
        "base_url": "https://ark.ap-southeast.bytepluses.com/api/coding/v3",
        "models": ["deepseek-v4-pro-260425"],
        "key_env": "BYTEDANCE_API_KEY",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "o3-mini"],
        "key_env": "OPENAI_PROVIDER_API_KEY",
    },
    "custom": {
        "label": "Custom (OpenAI-compatible)",
        "base_url": "",
        "models": [],
        "key_env": None,
    },
}
