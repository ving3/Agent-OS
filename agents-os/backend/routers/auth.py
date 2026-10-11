# -*- coding: utf-8 -*-
"""Agent OS — Router d'authentification (login, signup)"""
from fastapi import APIRouter, Response, Request
from database import get_db, hash_password, generate_token, get_user_count
from schemas import LoginRequest, SignupRequest, TokenResponse, ErrorResponse

router = APIRouter(prefix="/api", tags=["auth"])


@router.post("/login", response_model=TokenResponse | ErrorResponse)
def login(body: LoginRequest, response: Response) -> dict:
    email = body.email.strip().lower()
    conn = get_db()
    row = conn.execute(
        "SELECT id, name, email, role, disabled FROM users WHERE email = ?", (email,)
    ).fetchone()
    if not row or row[4]:
        conn.close()
        response.status_code = 401
        return {"error": "Email ou mot de passe incorrect"}

    if row[3] == "pending":
        conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (row[0],))
        conn.commit()
        row = (row[0], row[1], row[2], "admin", 0)

    stored = conn.execute("SELECT password_hash FROM users WHERE id = ?", (row[0],)).fetchone()[0]
    if stored != hash_password(body.password):
        conn.close()
        response.status_code = 401
        return {"error": "Email ou mot de passe incorrect"}

    token = generate_token()
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, row[0]))
    conn.commit()
    conn.close()
    return {
        "token": token,
        "user": {"id": row[0], "name": row[1], "email": row[2], "role": row[3],
                 "permissions": {"panels": [], "agents": []}},
    }


@router.post("/signup", response_model=TokenResponse | ErrorResponse)
def signup(body: SignupRequest, response: Response) -> dict:
    name = body.name.strip()
    email = body.email.strip().lower()
    if not name or not email or not body.password:
        response.status_code = 400
        return {"error": "Tous les champs sont obligatoires"}
    if len(body.password) < 6:
        response.status_code = 400
        return {"error": "Mot de passe trop court (min 6 caractères)"}

    conn = get_db()
    if conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        conn.close()
        response.status_code = 409
        return {"error": "Cet email est déjà utilisé"}
    if conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone():
        conn.close()
        response.status_code = 409
        return {"error": "Ce nom est déjà utilisé"}

    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    role = "admin" if count == 0 else "user"
    conn.execute(
        "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
        (name, email, hash_password(body.password), role),
    )
    conn.commit()
    uid = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()[0]
    token = generate_token()
    conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, uid))
    conn.commit()
    conn.close()
    return {
        "token": token,
        "user": {"id": uid, "name": name, "email": email, "role": role,
                 "permissions": {"panels": [], "agents": []}},
    }
