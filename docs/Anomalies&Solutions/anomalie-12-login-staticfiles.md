# Anomalie 12 — Page login affiche le dashboard sans authentification

> **Date** : 2026-10-11
> **Contexte** : Architecture v3 (FastAPI + TypeScript SPA)
> **Impact** : Bloquant — Impossible de se connecter, pas de formulaire login/signup
> **Statut** : ✅ Résolu

---

## 1. Symptôme

```text
GET https://agents-os.apps.okdsnoapps.vmapps.home/login
→ Affiche le dashboard SPA (sidebar, widgets, etc.)
→ Pas de formulaire de connexion
→ Impossible de créer un compte admin
```

## 2. Analyse

### Cause #1 — StaticFiles écrase les routes

Le `backend/main.py` montait les fichiers statiques à la racine :

```python
# AVANT — ligne 74
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
```

FastAPI traite les `mount` comme des sous-applications ASGI. Un `mount("/", ...)` capture **toutes** les requêtes avant que les `@app.get("/login")` ne soient évaluées. Résultat : toutes les pages servent `index.html` (le SPA).

### Cause #2 — Le SPA n'a pas de page login

Le SPA (`main.ts`) affichait directement le dashboard (`renderShell()`) sans vérifier l'authentification. Même sans token, l'interface dashboard s'affichait (sans données, mais avec la sidebar et les widgets vides).

### Chaîne d'impact

```
app.mount("/", StaticFiles) 
    → écrase toutes les routes @app.get()
    → /login sert index.html (le SPA)
    → SPA → renderShell() sans vérifier le token
    → Dashboard affiché sans auth
    → Aucun formulaire login visible
```

## 3. Choix possibles

| Solution | Description | Complexité |
|----------|-------------|------------|
| **A** — StaticFiles à `/static` + SPA avec login | Mount à `/static`, le SPA gère l'auth (login page inline) | Faible |
| **B** — Pages login/signup séparées | Servir des HTML distincts pour login/signup, SPA pour le dashboard | Moyenne |
| **C** — Retirer StaticFiles, servir manuellement | Routes explicites pour chaque fichier statique | Élevée |

## 4. Solution appliquée (A)

### 4.1 Fix backend — StaticFiles à `/static`

```python
# backend/main.py — ligne 74
# AVANT
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

# APRÈS
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
```

- Retrait de `html=True` (ne pas servir `index.html` automatiquement)
- Montage à `/static` au lieu de `/`
- Les routes `@app.get("/login")`, `@app.get("/dashboard")` redeviennent prioritaires

### 4.2 Fix frontend — Références `/static/`

```html
<!-- frontend/dist/index.html -->
<!-- AVANT -->
<link rel="stylesheet" href="/app.css">
<script src="/app.js"></script>

<!-- APRÈS -->
<link rel="stylesheet" href="/static/app.css">
<script src="/static/app.js"></script>
```

### 4.3 Fix SPA — Page login inline

Le SPA (`main.ts`) vérifie la présence d'un token cookie au démarrage :

```typescript
function init(): void {
  const token = getCookie("token");
  if (!token) {
    renderLoginPage();  // ← affiche le formulaire login/signup
    return;
  }

  fetch("/api/status", { headers: { "Authorization": `Bearer ${token}` } })
    .then(r => r.ok ? r.json() : null)
    .then(data => {
      if (!data || data.error) { renderLoginPage(); return; }
      renderShell();  // ← dashboard normal
      ...
    })
    .catch(() => renderLoginPage());
}
```

**Pages login/signup** : rendues directement dans le DOM (`app.innerHTML`) avec le design system CSS :

- Formulaire login : email + password → `POST /api/login`
- Formulaire signup : nom + email + password → `POST /api/signup`
- Navigation entre les deux via lien
- Gestion des erreurs (champs vides, email déjà utilisé, mot de passe incorrect)
- Après succès : `document.cookie = token=...` + rappel `init()`

## 5. Résultat

| Vérification | Avant | Après |
|-------------|-------|-------|
| `GET /login` | Dashboard SPA | ✅ Formulaire login |
| `GET /signup` | Dashboard SPA | ✅ Formulaire signup |
| `POST /api/login` | Fonctionnel | ✅ Redirige vers dashboard |
| `POST /api/signup` | Fonctionnel | ✅ Crée compte + redirige |
| `GET /dashboard` (avec token) | Dashboard | ✅ Dashboard avec 8 panels |
| `GET /dashboard` (sans token) | Dashboard sans données | ✅ Redirige vers login |
| `GET /static/app.js` | 404 | ✅ 200 (77 KB) |
| `GET /static/app.css` | 404 | ✅ 200 (35 KB) |

## 6. Leçon

1. **Ne jamais monter `StaticFiles` à `/` dans FastAPI** — cela écrase toutes les routes définies avec `@app.get()`. Toujours utiliser un préfixe (`/static`, `/assets`).

2. **Toujours vérifier l'auth au démarrage du SPA** — le SPA doit détecter l'absence de token et afficher une page de login avant de rendre l'interface principale.

## Fichiers concernés

- `agents-os/backend/main.py` (StaticFiles mount)
- `agents-os/frontend/src/main.ts` (auth detection + login page)
- `agents-os/frontend/dist/index.html` (paths /static/)
- `agents-os/frontend/dist/app.css` (auth page styles)
