# -*- coding: utf-8 -*-
"""
Agent OS — Application FastAPI
Backend d'orchestration des agents IA avec API REST documentée.
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, RedirectResponse

from config import HOST, PORT, DATA_DIR, STATIC_DIR
from database import init_db, get_db
from routers import auth, dashboard, chat, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()
    yield


app = FastAPI(
    title="Agentic OS API",
    version="3.0.0",
    description="Backend d'orchestration des agents IA — API REST documentée",
    lifespan=lifespan,
)

# ── Routes API ─────────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(chat.router)
app.include_router(admin.router)


# ── Pages HTML (SPA fallback) ──────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/login")
@app.get("/signup")
@app.get("/")
@app.get("/dashboard")
@app.get("/admin")
def serve_spa(request: Request, response: Response):
    """Sert le fichier index.html pour toutes les routes SPA."""
    token = request.cookies.get("token")
    # Auth redirect: /admin and /dashboard require login
    if request.url.path in ("/dashboard", "/admin"):
        from database import get_user_from_token
        if not get_user_from_token(token):
            return RedirectResponse(url="/login", status_code=302)

    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"message": "Agentic OS API — Frontend non trouvé. Utilisez les endpoints /api/*"}


@app.get("/logout")
def logout(response: Response):
    response.delete_cookie("token", path="/", samesite="lax", httponly=True)
    return RedirectResponse(url="/login", status_code=302)


# ── Fichiers statiques (CSS, JS, assets) ───────────────────────────────────────

if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Point d'entrée CLI ─────────────────────────────────────────────────────────

def main():
    import uvicorn
    print(f"[Agentic OS] FastAPI en écoute sur http://{HOST}:{PORT}")
    print(f"[Agentic OS] Base de données : {DATA_DIR}/agentic_os.db")
    print(f"[Agentic OS] Frontend statique : {STATIC_DIR}")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
