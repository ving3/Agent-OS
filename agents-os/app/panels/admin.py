# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Administration
Gestion des utilisateurs (CRUD), permissions, creation/suppression d'agents.
Routes gerees par dashboard/router.py :
  GET  /api/users → liste des utilisateurs (admin only)
  POST /api/admin/user/create → creer un utilisateur
  POST /api/admin/user/update → modifier role/statut
  POST /api/admin/user/delete → supprimer un utilisateur
  POST /api/admin/user/permissions → gerer les permissions
  POST /api/admin/agent/create → creer un agent via Hermes pod exec
  POST /api/admin/agent/delete → supprimer un agent
  GET  /admin → page HTML d'administration (ADMIN_HTML)
  GET  /admin/user/<id> → detail d'un utilisateur

Template HTML : dashboard/templates.py → ADMIN_HTML
"""
