# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Chat (Chat Agents)
Interface de chat contextuel avec chaque agent.
Routes gerees par dashboard/router.py :
  POST /v1/chat/completions → API OpenAI-compatible (model, messages)
  POST /api/chat → chat simplifie (profile, message)
  GET  /v1/models → liste des modeles disponibles
"""
