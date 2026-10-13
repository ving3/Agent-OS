# Architecture v3 — Agentic OS (FastAPI + TypeScript)

> **Date** : 2026-10-11  
> **Version** : 3.0.0  
> **Remplace** : `docs/00-architecture.md`, `docs/06-architecture-flux.md`

---

## 1. Vue d'ensemble

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Agentic OS v3                                 │
│                                                                       │
│  ┌─────────────────────┐          ┌──────────────────────────────┐   │
│  │    FRONTEND          │  HTTP    │    BACKEND                    │   │
│  │    TypeScript         │◄───────►│    Python / FastAPI           │   │
│  │    esbuild → IIFE     │  JSON   │    uvicorn                    │   │
│  │                       │         │                               │   │
│  │  store.ts (Observable)│         │  schemas.py (Pydantic)        │   │
│  │  types.ts ←── miroir ─│─────────│──► types.ts                   │   │
│  │                       │         │                               │   │
│  │  ui/shell.ts          │         │  routers/auth.py              │   │
│  │  ui/widgets.ts        │         │  routers/dashboard.py         │   │
│  │  components/*.ts      │         │  routers/chat.py              │   │
│  │                       │         │  routers/admin.py             │   │
│  │  SPA fallback ←───────│─────────│──► StaticFiles(app.css, js)   │   │
│  └───────────────────────┘         └──────────────┬───────────────┘   │
│                                                    │                   │
│                                          ┌─────────▼──────────┐       │
│                                          │  Hermes Agent API  │       │
│                                          │  http://hermes:8777 │       │
│                                          │  /v1/chat/complet.  │       │
│                                          └────────────────────┘       │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. Contrat API

La **source unique de vérité** du contrat API est `backend/schemas.py` (Pydantic).
Le frontend TypeScript reflète ces types dans `frontend/src/types.ts`.

| Endpoint | Méthode | Pydantic | TypeScript | Auth |
|----------|---------|----------|------------|------|
| `/health` | GET | - | - | Non |
| `/api/login` | POST | `LoginRequest → TokenResponse` | `UserInfo` | Non |
| `/api/signup` | POST | `SignupRequest → TokenResponse` | `UserInfo` | Non |
| `/api/status` | GET | `SystemStatus` | `SystemStatus` | Token |
| `/api/profiles` | GET | `ProfileListResponse` | `AgentProfile[]` | Token |
| `/api/profile/{name}` | GET | `ProfileResponse` | - | Token |
| `/api/skills` | GET | `SkillListResponse` | `SkillInfo[]` | Token |
| `/api/chat` | POST | `ChatRequest → ChatResponse` | `ChatResponse` | Token |
| `/v1/chat/completions` | POST | `ChatCompletionRequest → ChatCompletionResponse` | `ChatCompletionResponse` | Token |
| `/v1/models` | GET | `ModelListResponse` | `ModelInfo[]` | Token |
| `/api/users` | GET | `UserListResponse` | `UserRecord[]` | Admin |
| `/api/admin/user/create` | POST | `CreateUserRequest → SuccessResponse` | - | Admin |
| `/api/admin/user/update` | POST | `UpdateUserRequest → SuccessResponse` | - | Admin |
| `/api/admin/user/permissions` | POST | `UpdatePermissionsRequest` | - | Admin |
| `/api/admin/user/delete` | POST | `DeleteUserRequest → SuccessResponse` | - | Admin |
| `/api/admin/agent/create` | POST | `CreateAgentRequest → SuccessResponse` | - | Admin |
| `/api/admin/agent/delete` | POST | `DeleteAgentRequest → SuccessResponse` | - | Admin |

### Règle d'évolution

1. Toute modification du contrat commence par `backend/schemas.py`
2. Le type TypeScript correspondant est mis à jour dans `frontend/src/types.ts`
3. Les deux doivent rester synchronisés — les tests d'intégration vérifient la compatibilité

## 3. Architecture Frontend

### 3.1 Stack technique

| Couche | Technologie |
|--------|------------|
| Langage | TypeScript 5.6+ |
| Bundler | esbuild (build.mjs) |
| Format de sortie | IIFE bundle → `dist/app.js` (1 fichier) |
| CSS | `dist/app.css` (design system CSS custom properties) |
| State management | Pattern Observable (store.ts) |
| Routing | Client-side SPA (hash-free, pushState) |

### 3.2 Arborescence

```
frontend/
├── package.json            ← Dépendances (esbuild, typescript)
├── tsconfig.json           ← Strict, ES2022, DOM
├── build.mjs               ← Configuration esbuild (watch/build)
├── src/
│   ├── main.ts             ← Point d'entrée : init, routing, panels
│   ├── types.ts            ← Types TypeScript (miroir schemas.py)
│   ├── store.ts            ← State global Observable (polling 5s)
│   ├── components/
│   │   ├── dashboard.ts    ← Panel Dashboard (widgets, agents, feed)
│   │   ├── admin.ts        ← Panel Admin (RBAC, users, system)
│   │   ├── chat.ts         ← Panel Chat (streaming, tool calls)
│   │   ├── skills.ts       ← Panel Skills (catalogue, config)
│   │   ├── memory.ts       ← Panel Memory (explorer, CRUD)
│   │   ├── canvas.ts       ← Panel Canvas (blocks, undo/redo)
│   │   ├── graph.ts        ← Panel Graph (nodes, edges, force)
│   │   └── kanban.ts       ← Panel Kanban (drag-drop, tasks)
│   └── ui/
│       ├── shell.ts        ← Sidebar, Topbar, navigation
│       └── widgets.ts      ← Widget grid, métriques, charts, feed
└── dist/
    ├── index.html           ← Coquille HTML (mount point #app)
    └── app.css              ← Design system complet
```

### 3.3 Cycle de vie d'un panel

```
1. store.setPanel("overview")     ← Changement de panel
2. store.subscribe() → callback   ← Notification du changement
3. main.ts → switch(panel)        ← Routeur : rendu du composant
4. component.renderDashboard()    ← Rendu du composant dans #aos-content
5. store.subscribe(onUpdate)      ← Le composant s'abonne aux changements
6. store.fetchPanelData(panel)    ← Chargement des données API
7. store.setStatus/Profiles/...   ← Mise à jour du state
8. onUpdate() → re-render         ← Mise à jour incrémentale du DOM
```

### 3.4 Gestion d'état

```typescript
// store.ts — Pattern Observable
class Store {
  private state: AppState;
  private listeners: Set<Listener>;

  subscribe(fn): () => void   // S'abonner aux changements
  getState(): AppState        // Lire l'état courant
  setPanel(panel): void       // Changer de panel
  setStatus(status): void     // Mettre à jour le statut système
  addActivity(event): void    // Ajouter un événement au feed
  addMetric(snapshot): void   // Ajouter un snapshot de métriques
  startPolling(ms): void      // Démarrer le polling périodique
}
```

## 4. Architecture Backend

### 4.1 Stack technique

| Couche | Technologie |
|--------|------------|
| Framework | FastAPI 0.115+ |
| Serveur | uvicorn |
| Validation | Pydantic v2 |
| Base de données | SQLite (fichier local `/data/agentic_os.db`) |
| Client HTTP | httpx (appels à Hermes API) |

### 4.2 Arborescence

```
backend/
├── main.py                  ← FastAPI app, SPA fallback, static files
├── config.py                ← Variables d'environnement, constantes
├── database.py              ← SQLite init, CRUD helpers
├── schemas.py               ← Pydantic models (contrat API)
├── routers/
│   ├── __init__.py
│   ├── auth.py              ← POST /api/login, /api/signup
│   ├── dashboard.py         ← GET /api/status, /api/profiles, /api/skills
│   ├── chat.py              ← POST /api/chat, /v1/chat/completions
│   └── admin.py             ← CRUD users, create/delete agents
└── services/
    ├── __init__.py
    └── hermes_client.py     ← Client Hermes, profils, skills
```

### 4.3 Flux d'une requête

```
1. Requête HTTP → FastAPI router
2. Auth middleware : extraction token (Cookie: token ou Authorization: Bearer)
3. Validation Pydantic : body/query params
4. Logique métier : database.py + services/hermes_client.py
5. Réponse Pydantic : sérialisation JSON automatique
6. Code HTTP : 200/400/401/403/409/500 selon le cas
```

### 4.4 Sécurité

| Mécanisme | Détail |
|-----------|--------|
| Auth | Token JWT-like (secrets.token_hex) stocké en base sessions |
| Transport | Cookie HttpOnly + SameSite=Lax |
| RBAC | Rôle `admin`/`user` + permissions par panel/agent |
| Validation | Pydantic strict (types, longueurs, patterns) |
| CORS | Non nécessaire (même origine, SPA servie par FastAPI) |

## 5. Déploiement

### 5.1 Docker multi-stage

```
Stage 1: Node.js 22
  → npm install (esbuild, typescript)
  → npm run build → dist/app.js

Stage 2: Python 3.11-slim
  → pip install (fastapi, uvicorn, httpx, pydantic)
  → COPY backend/ + frontend/dist/
  → CMD: python -m backend.main
```

### 5.2 OpenShift BuildConfig

```yaml
# argocd/manifests/agents-os/buildconfig.yaml
source:
  type: Binary
  binary: {}
strategy:
  type: Docker
  dockerStrategy:
    dockerfilePath: Dockerfile
output:
  to:
    kind: ImageStreamTag
    name: agents-os:latest
```

### 5.3 ArgoCD

```
argocd/apps/agents-os-app.yaml
  → path: argocd/manifests/agents-os
  → namespace: ai
  → syncPolicy: automated (prune + selfHeal)
```

## 6. Panels (état d'implémentation)

| # | Panel | Route | Composant | Statut |
|---|-------|-------|-----------|--------|
| 1 | Dashboard | `overview` | `components/dashboard.ts` | ✅ Implémenté |
| 2 | Administration | `admin` | `components/admin.ts` | ✅ Implémenté |
| 3 | Chat Agents | `chat` | `components/chat.ts` | ✅ Implémenté |
| 4 | Skills | `skills` | `components/skills.ts` | ✅ Implémenté |
| 5 | Mémoire | `memory` | `components/memory.ts` | ✅ Implémenté |
| 6 | Canvas | `canvas` | `components/canvas.ts` | ✅ Implémenté |
| 7 | Graphe | `graph` | `components/graph.ts` | ✅ Implémenté |
| 8 | Kanban | `kanban` | `components/kanban.ts` | ✅ Implémenté |
| 9 | n8n Orchestration | `n8n` | `components/n8n.ts` | ✅ Implémenté |

## 7. Flux de données inter-panels

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│ Dashboard │    │  Admin   │    │  Chat    │
│ (métrics) │    │ (RBAC)   │    │ (stream) │
└─────┬─────┘    └────┬─────┘    └────┬─────┘
      │               │               │
      └───────┬───────┴───────┬───────┘
              │               │
        ┌─────▼─────┐   ┌─────▼─────┐
        │   Store   │   │  Skills   │
        │ (Observ.) │   │ (plugins) │
        └─────┬─────┘   └─────┬─────┘
              │               │
      ┌───────┼───────┐       │
      │       │       │       │
  ┌───▼──┐ ┌──▼──┐ ┌──▼───┐  │
  │Memory│ │Canvas│ │Graph │  │
  │(RAG) │ │(edit)│ │(viz) │  │
  └──────┘ └──┬───┘ └──────┘  │
              │                │
         ┌────▼────┐           │
         │ Kanban  │◄──────────┘
         │ (tasks) │
         └─────────┘
```

## 8. Documentation connexe

| Document | Description |
|----------|------------|
| `docs/Anomalies&Solutions/` | 10 anomalies documentées (déploiement ArgoCD) |
| `docs/01-manifests/` | ⚠️ DEPRECATED — Remplacé par `argocd/manifests/` |
| `Suivi-Action.md` | Suivi des actions de migration GitOps |
| `argocd/` | Applications et manifests ArgoCD (App of Apps) |
