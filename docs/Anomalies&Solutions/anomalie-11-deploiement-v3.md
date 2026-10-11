# Anomalie 11 — Déploiement v3 : WORKDIR + CSS manquant

> **Date** : 2026-10-11
> **Contexte** : Déploiement de l'architecture v3 (FastAPI + TypeScript)
> **Impact** : Bloquant (CrashLoopBackOff) puis fonctionnel après 2 corrections
> **Statut** : ✅ Résolu

---

## 1. Anomalie 11a — ModuleNotFoundError: No module named 'config'

### Contexte

Le Dockerfile v3 utilise `CMD ["python", "-m", "backend.main"]` pour lancer l'application.
`backend/main.py` importe `from config import HOST, PORT, DATA_DIR, STATIC_DIR` qui cherche
`config.py` dans le répertoire courant, pas dans le package `backend`.

### Symptôme

```text
CrashLoopBackOff
Traceback (most recent call last):
  File "<frozen runpy>", line 198, in _run_module_as_main
  File "<frozen runpy>", line 88, in _run_code
  File "/opt/app/backend/main.py", line 12, in <module>
    from config import HOST, PORT, DATA_DIR, STATIC_DIR
ModuleNotFoundError: No module named 'config'
```

### Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — Changer WORKDIR | `WORKDIR /opt/app/backend` + `CMD ["python", "main.py"]` |
| **B** — Corriger les imports | `from backend.config import ...` dans tous les fichiers |
| **C** — Ajouter sys.path | `sys.path.insert(0, os.path.dirname(__file__))` |

### Solution appliquée (A)

```dockerfile
# AVANT
CMD ["python", "-m", "backend.main"]

# APRÈS
WORKDIR /opt/app/backend
CMD ["python", "main.py"]
```

### Résultat

Le pod démarre correctement avec `python main.py` depuis `/opt/app/backend/`.
Tous les imports relatifs (`from config import ...`, `from database import ...`)
fonctionnent car les fichiers sont dans le même répertoire que le WORKDIR.

---

## 2. Anomalie 11b — CSS 404 (app.css manquant)

### Contexte

Le Dockerfile ne copiait que `frontend/dist/index.html` mais pas `frontend/dist/app.css`.
Le fichier CSS était présent dans le dépôt git mais n'était pas inclus dans l'image Docker.

### Symptôme

```text
curl -I https://agents-os.apps.okdsnoapps.vmapps.home/app.css
HTTP 404 Not Found
```

La page dashboard se chargeait sans styles (layout cassé, sidebar invisible, couleurs absentes).

### Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — Copier tout dist/ | `COPY frontend/dist/ ./frontend/dist/` |
| **B** — Ajouter app.css explicitement | `COPY frontend/dist/app.css ./frontend/dist/` |
| **C** — Inclure CSS dans JS | Bundler le CSS via esbuild |

### Solution appliquée (A)

```dockerfile
# AVANT
COPY frontend/dist/index.html ./frontend/dist/

# APRÈS
COPY frontend/dist/ ./frontend/dist/
```

### Résultat

Tous les fichiers statiques de `frontend/dist/` sont copiés dans l'image.
`app.css` est servi avec HTTP 200 (35 KB).

---

## 3. Résumé du déploiement

| Étape | Build | Résultat |
|-------|-------|----------|
| Build #19 | Docker v3 initial | CrashLoopBackOff (ModuleNotFoundError) |
| Build #20 | Fix WORKDIR | Running, mais CSS 404 |
| Build #21 | Fix COPY dist/ | ✅ Tout fonctionne |

### Vérification finale

| Endpoint | Résultat |
|----------|----------|
| `GET /health` | ✅ `{"status":"ok"}` |
| `GET /` (index.html) | ✅ HTTP 200 |
| `GET /app.js` | ✅ HTTP 200 (77 KB) |
| `GET /app.css` | ✅ HTTP 200 (35 KB) |
| `GET /dashboard` | ✅ HTTP 302 → login (auth OK) |
| `POST /api/login` | ✅ Token JWT reçu |
| `GET /api/status` | ✅ JSON complet |
| `GET /api/profiles` | ✅ 7 profils |
| `GET /api/skills` | ✅ 58 compétences |
| `GET /v1/models` | ✅ 5 modèles |

---

## Fichiers concernés

- `agents-os/Dockerfile` (WORKDIR + COPY fix)
