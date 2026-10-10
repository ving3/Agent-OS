# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Memoire (Agent Memory Viewer)
Affiche la memoire persistante de chaque agent.
Donnees chargees depuis le repertoire /opt/data/profiles/<name>/memories/.
Routes gerees par dashboard/router.py :
  GET  /api/profiles → inclut le champ 'memory' pour chaque profil
  GET  /api/profile/<name> → memoire d'un agent specifique
"""
