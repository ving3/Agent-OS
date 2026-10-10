# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Skills (Explorateur de competences)
Liste les competences (SKILL.md) disponibles dans /opt/data/skills/.
"""
from hermes_client import list_skills


def handle_skills(handler):
    """GET /api/skills — Liste de toutes les competences enregistrees."""
    handler._send_json({"skills": list_skills()})
