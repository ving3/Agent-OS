# -*- coding: utf-8 -*-
"""
Agentic OS — Panneau Administration
Routes : /api/users, /admin/user/<id>, /api/admin/user/*
         /api/admin/agent/create, /api/admin/agent/delete
"""
from .handler import (
    handle_list_users, handle_get_user,
    handle_create_user, handle_update_user_permissions,
    handle_update_user, handle_delete_user,
    handle_create_agent, handle_delete_agent,
)
