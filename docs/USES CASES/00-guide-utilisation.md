# Agent OS — Use Cases

> Guide d'utilisation détaillé avec schémas, flux API et exemples concrets.
> Version 3.0 — Architecture FastAPI + TypeScript SPA
> Cluster : `okdsnoapps.vmapps.home`

---

## Table des matières

1. [UC-01 — Premier accès et création du compte admin](#uc-01--premier-accès-et-création-du-compte-admin)
2. [UC-02 — Connexion au dashboard](#uc-02--connexion-au-dashboard)
3. [UC-03 — Chat avec un agent IA](#uc-03--chat-avec-un-agent-ia)
4. [UC-04 — Création d'un agent personnalisé](#uc-04--création-dun-agent-personnalisé)
5. [UC-05 — Suppression d'un agent](#uc-05--suppression-dun-agent)
6. [UC-06 — Gestion des tâches Kanban](#uc-06--gestion-des-tâches-kanban)
7. [UC-07 — Exploration de la mémoire d'un agent](#uc-07--exploration-de-la-mémoire-dun-agent)
8. [UC-08 — Consultation du catalogue de Skills](#uc-08--consultation-du-catalogue-de-skills)
9. [UC-09 — Canvas : brainstorming visuel](#uc-09--canvas--brainstorming-visuel)
10. [UC-10 — Graphe des relations entre agents](#uc-10--graphe-des-relations-entre-agents)
11. [UC-11 — Administration : gestion des utilisateurs](#uc-11--administration--gestion-des-utilisateurs)
12. [UC-12 — Administration : permissions par utilisateur](#uc-12--administration--permissions-par-utilisateur)
13. [UC-13 — Dashboard : surveillance des métriques](#uc-13--dashboard--surveillance-des-métriques)

---

## UC-01 — Premier accès et création du compte admin

### Description
Un nouvel utilisateur accède à Agent OS pour la première fois. Aucun compte n'existe
encore dans la base de données. Le premier compte créé devient automatiquement
**administrateur**.

### Acteurs
- **Utilisateur** (futur admin)

### Préconditions
- L'application est déployée et accessible
- La base de données SQLite est vide (aucun utilisateur)

### Flux

```
┌──────────┐     GET /        ┌──────────┐     index.html     ┌──────────┐
│  Browser  │ ──────────────► │  FastAPI  │ ────────────────► │   SPA    │
│           │                 │  (serve)  │                   │  (JS)    │
│           │ ◄────────────── │           │ ◄──────────────── │          │
│           │  200 + SPA JS   │           │   renderLogin()   │          │
└─────┬────┘                 └──────────┘                   └──────────┘
      │
      │  L'utilisateur clique "Créer un compte"
      │
      ▼
┌──────────┐   POST /api/signup   ┌──────────┐   INSERT users   ┌──────────┐
│  SPA     │ ──────────────────► │  FastAPI  │ ──────────────► │  SQLite  │
│ (form)   │                     │  /signup  │                  │          │
│          │ ◄────────────────── │           │ ◄─────────────── │          │
│  {token} │   200 + token       │  count=0  │   role=admin     │          │
└─────┬────┘                     └──────────┘                  └──────────┘
      │
      │  document.cookie = token
      │
      ▼
┌──────────┐
│ Dashboard│  8 panels accessibles
│ (admin)  │
└──────────┘
```

### Requêtes API

| Étape | Méthode | Endpoint | Body | Réponse |
|-------|---------|----------|------|---------|
| 1. Charger la page | GET | `/` | - | `index.html` (SPA) |
| 2. SPA détecte pas de token | - | - | - | `renderLoginPage()` |
| 3. Créer le compte | POST | `/api/signup` | `{"name":"Admin","email":"a@l.h","password":"..."}` | `{"token":"...","user":{...}}` |
| 4. Redirection auto | - | - | - | Dashboard |

### Exemple

```bash
# Étape 1 : Créer le premier compte (admin automatique)
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/api/signup \
  -H "Content-Type: application/json" \
  -d '{"name":"Jean Admin","email":"admin@local.home","password":"SecurePass123"}'

# Réponse
{
  "token": "a1b2c3d4...",
  "user": {
    "id": 1,
    "name": "Jean Admin",
    "email": "admin@local.home",
    "role": "admin",
    "permissions": {"panels": [], "agents": []}
  }
}
```

### Résultat attendu
- L'utilisateur est redirigé vers le dashboard
- Les 8 panneaux sont visibles dans la sidebar (rôle admin = accès complet)
- Le bouton "Administration" est visible

---

## UC-02 — Connexion au dashboard

### Description
Un utilisateur existant se connecte à Agent OS avec son email et mot de passe.

### Acteurs
- **Utilisateur** (admin ou user)

### Flux

```
┌──────────┐   POST /api/login    ┌──────────┐   SELECT users   ┌──────────┐
│  SPA     │ ──────────────────► │  FastAPI  │ ──────────────► │  SQLite  │
│ (login)  │                     │  /login   │                  │          │
│          │ ◄────────────────── │           │ ◄─────────────── │          │
│          │   200 + token       │  hash OK  │   user found     │          │
└─────┬────┘                     └──────────┘                  └──────────┘
      │
      │  document.cookie = token
      │  init() → fetch /api/status → renderShell()
      ▼
┌──────────┐   GET /api/status    ┌──────────┐
│  SPA     │ ──────────────────► │  FastAPI  │
│ (dash)   │ ◄────────────────── │           │
│          │   SystemStatus      │           │
└──────────┘                     └──────────┘
```

### Exemple

```bash
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/api/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@local.home","password":"SecurePass123"}'

# Réponse
{
  "token": "e5f6g7h8...",
  "user": {"id":1,"name":"Jean Admin","email":"admin@local.home","role":"admin"}
}
```

---

## UC-03 — Chat avec un agent IA

### Description
L'utilisateur sélectionne un agent dans le panneau Chat, saisit un message et reçoit
une réponse générée par l'IA. Les tool calls (appels d'outils) sont affichés dans
des panneaux repliables.

### Acteurs
- **Utilisateur**
- **Agent IA** (ex: `architect`, `senior-dev`)

### Flux

```
┌──────────┐  GET /api/profiles   ┌──────────┐
│  SPA     │ ──────────────────► │  FastAPI  │
│ (chat)   │ ◄────────────────── │           │
│          │  [architect, ...]   │           │
└─────┬────┘                     └──────────┘
      │
      │  L'utilisateur sélectionne "architect"
      │  Saisit : "Propose une architecture microservices"
      │
      ▼
┌──────────┐  POST /v1/chat/completions  ┌──────────┐  POST /v1/chat/..  ┌──────────┐
│  SPA     │ ──────────────────────────► │  FastAPI  │ ────────────────► │  Hermes  │
│          │ ◄────────────────────────── │  /chat    │ ◄──────────────── │  Agent   │
│          │  {choices:[{message:...}]}  │           │   réponse LLM     │  :8777   │
└──────────┘                             └──────────┘                   └──────────┘
```

### Exemple

```bash
# Envoyer un message à l'agent "architect"
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Cookie: token=e5f6g7h8..." \
  -d '{
    "model": "hermes-architect",
    "messages": [
      {"role": "user", "content": "Propose une architecture microservices pour une app e-commerce"}
    ]
  }'

# Réponse
{
  "id": "chatcmpl-1234567890",
  "object": "chat.completion",
  "model": "hermes-architect",
  "choices": [{
    "message": {
      "role": "assistant",
      "content": "Voici une architecture microservices recommandée :\n\n1. **API Gateway** ..."
    },
    "finish_reason": "stop"
  }]
}
```

### Résultat attendu
- La réponse de l'agent s'affiche dans la zone de chat
- Les tool calls éventuels apparaissent dans des panneaux repliables (🔧)
- Le compteur de requêtes dans la topbar s'incrémente

---

## UC-04 — Création d'un agent personnalisé

### Description
Un administrateur crée un nouvel agent IA personnalisé depuis le panneau Administration.
L'agent est créé dans le système de fichiers du pod Hermes.

### Acteurs
- **Administrateur**

### Préconditions
- Être connecté en tant qu'admin
- Le pod Hermes est en cours d'exécution
- Maximum 50 agents

### Flux

```
┌──────────┐  POST /api/admin/agent/create  ┌──────────┐  kubectl exec    ┌──────────┐
│  SPA     │ ─────────────────────────────► │  FastAPI  │ ──────────────► │  Hermes  │
│ (admin)  │                                │  /admin   │                 │  Pod     │
│          │ ◄───────────────────────────── │           │ ◄────────────── │          │
│          │  {success:true}                │           │  mkdir + files  │          │
└──────────┘                                └──────────┘                 └──────────┘
```

### Exemple

```bash
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/api/admin/agent/create \
  -H "Content-Type: application/json" \
  -b "token=e5f6g7h8..." \
  -d '{
    "name": "security-expert",
    "emoji": "🛡️",
    "color": "#f85149",
    "description": "Expert en sécurité applicative, audits et pentests"
  }'

# Réponse
{"success": true}
```

### Fichiers créés sur le pod Hermes

```
/opt/data/profiles/security-expert/
├── SOUL.md        ← Description et rôle de l'agent
└── config.yaml    ← Configuration du modèle LLM
```

---

## UC-05 — Suppression d'un agent

### Description
Un administrateur supprime un agent personnalisé (non-intégré) depuis le panneau
Administration. Une confirmation est demandée.

### Acteurs
- **Administrateur**

### Flux

```
┌──────────┐  Clique "✕ Supprimer"  ┌──────────┐
│  SPA     │ ─────────────────────► │  Modal   │
│ (admin)  │                        │  confirm │
│          │ ◄───────────────────── │          │
│          │  "Tapez le nom pour    │          │
│          │   confirmer"           │          │
└─────┬────┘                        └──────────┘
      │
      │  Confirmation
      ▼
┌──────────┐  POST /api/admin/agent/delete  ┌──────────┐  kubectl exec    ┌──────────┐
│  SPA     │ ─────────────────────────────► │  FastAPI  │ ──────────────► │  Hermes  │
│          │ ◄───────────────────────────── │           │ ◄────────────── │  Pod     │
│          │  {success:true}                │           │  rm -rf profile │          │
└──────────┘                                └──────────┘                 └──────────┘
```

### Exemple

```bash
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/api/admin/agent/delete \
  -H "Content-Type: application/json" \
  -b "token=e5f6g7h8..." \
  -d '{"name":"security-expert"}'

# Réponse
{"success": true}
```

---

## UC-06 — Gestion des tâches Kanban

### Description
L'utilisateur gère des missions via le tableau Kanban à 4 colonnes (À faire,
En cours, Review, Terminé). Les tâches sont persistées dans le `localStorage`.

### Acteurs
- **Utilisateur** (tout rôle)

### Flux

```
┌──────────┐  + Ajouter une mission  ┌──────────┐
│  SPA     │ ──────────────────────► │  Modal   │
│ (kanban) │                         │  create  │
│          │ ◄────────────────────── │          │
│          │  localStorage save      │          │
└──────────┘                         └──────────┘

┌──────────┐  Drag & Drop           ┌──────────┐
│  Colonne │ ─────────────────────► │  Colonne │
│  "À faire"│                        │ "En cours"│
│          │ ◄────────────────────── │          │
│          │  task.status = progress │          │
└──────────┘                         └──────────┘
```

### Exemple de données

```json
[
  {
    "id": 1700000000001,
    "title": "Configurer l'authentification SSO",
    "agent": "architect",
    "status": "todo",
    "created": "2026-10-12T14:00:00Z"
  },
  {
    "id": 1700000000002,
    "title": "Implémenter le streaming SSE du chat",
    "agent": "senior-dev",
    "status": "progress",
    "created": "2026-10-12T13:00:00Z"
  }
]
```

---

## UC-07 — Exploration de la mémoire d'un agent

### Description
L'utilisateur consulte la mémoire persistante de chaque agent. Une recherche
sémantique permet de trouver des passages spécifiques.

### Acteurs
- **Utilisateur**

### Flux

```
┌──────────┐  GET /api/profiles     ┌──────────┐  read memories/   ┌──────────┐
│  SPA     │ ────────────────────► │  FastAPI  │ ────────────────► │  Hermes  │
│ (memory) │ ◄──────────────────── │           │ ◄──────────────── │  PVC     │
│          │  [{memory: "...",     │           │  memory.md       │          │
│          │    has_memory: true}] │           │                  │          │
└──────────┘                       └──────────┘                  └──────────┘
```

### Exemple de mémoire

```markdown
# Agent architect — Mémoire

## Décisions d'architecture
- 2026-10-10 : Choix de FastAPI pour le backend (performance, typage Pydantic)
- 2026-10-10 : Frontend TypeScript compilé avec esbuild (bundle IIFE 77KB)

## Patterns utilisés
- App of Apps pour ArgoCD
- Observable pattern pour le state management frontend
```

---

## UC-08 — Consultation du catalogue de Skills

### Description
L'utilisateur explore les 58 compétences disponibles, filtre par nom et consulte
les détails de chaque skill.

### Acteurs
- **Utilisateur**

### Flux

```
┌──────────┐  GET /api/skills        ┌──────────┐  read SKILL.md    ┌──────────┐
│  SPA     │ ────────────────────►  │  FastAPI  │ ────────────────► │  Hermes  │
│ (skills) │ ◄────────────────────  │           │ ◄──────────────── │  PVC     │
│          │  [{name,path,desc}]    │           │  rglob("SKILL.md")│         │
└──────────┘                        └──────────┘                   └──────────┘
```

### Exemple

```json
{
  "skills": [
    {"name": "github", "path": "github", "description": "GitHub integration"},
    {"name": "pdf", "path": "pdf", "description": "PDF document processing"},
    {"name": "test-driven-development", "path": "test-driven-development", "description": "TDD workflow"}
  ]
}
```

---

## UC-09 — Canvas : brainstorming visuel

### Description
L'utilisateur crée un espace de travail visuel avec des blocs de texte, code,
cartes et images. Les blocs sont déplaçables et connectables par des flèches.

### Acteurs
- **Utilisateur**

### Flux

```
┌──────────┐  +Texte / +Code        ┌──────────┐
│  SPA     │ ────────────────────► │  Canvas   │
│ (canvas) │                        │  (DOM)    │
│          │ ◄──────────────────── │           │
│          │  localStorage save     │           │
└──────────┘                        └──────────┘
```

### Exemple d'export JSON

```json
{
  "blocks": [
    {"id":"a1","type":"markdown","content":"# Idée principale\n...","x":40,"y":40,"w":320,"h":180},
    {"id":"a2","type":"code","content":"const api = new HermesClient()","x":400,"y":40,"w":320,"h":160}
  ],
  "connections": [
    {"from":"a1","to":"a2"}
  ]
}
```

### Raccourcis
- `Ctrl+Z` : Undo
- `Ctrl+Y` : Redo
- Double-clic sur un bloc : Édition
- 🔗 : Connecter deux blocs

---

## UC-10 — Graphe des relations entre agents

### Description
Visualisation interactive des agents et de leurs compétences sous forme de graphe
force-directed. Les relations sont calculées automatiquement par similarité sémantique
des profils (SOUL.md). Recherche et filtrage par type de nœud.

### Comment se construisent les relations ?

Le backend `/api/graph` analyse le contenu des profils agents pour établir
des relations réelles :

1. **Extraction de mots-clés** : chaque `SOUL.md` est parsé, les stopwords
   (fr/en) sont filtrés, les mots significatifs sont extraits
2. **Similarité cosinus** : calcul du score de similarité entre chaque paire d'agents
3. **Seuil minimal** : seules les relations avec un score > 5% sont conservées
4. **Concepts émergents** : les mots-clés apparaissant chez ≥ 2 agents deviennent
   des nœuds "concept" reliés aux agents concernés
5. **Skills** : les compétences sont reliées aux agents par compatibilité sémantique

### Acteurs
- **Utilisateur**

### Flux

```
┌──────────┐  GET /api/graph          ┌──────────┐  read SOUL.md     ┌──────────┐
│  SPA     │ ──────────────────────► │  FastAPI  │ ────────────────► │  Hermes  │
│ (graph)  │ ◄────────────────────── │           │ ◄──────────────── │  PVC     │
│          │  {nodes, edges}         │           │  cosine sim       │          │
└─────┬────┘                         └──────────┘                    └──────────┘
      │
      │  Force simulation (requestAnimationFrame)
      │  Rendu SVG des nœuds et arêtes
      ▼
┌──────────┐
│  Graph   │  ○──○──○
│  SVG     │   ╲╱
└──────────┘
```

### Types de nœuds

| Type | Icône | Couleur | Source |
|------|-------|---------|--------|
| Agent | 🤖 | Spécifique au profil | `/api/profiles` |
| Skill | 🧩 | Orange | `/api/skills` |
| Concept | 💡 | Violet | Mots-clés extraits |

### Types d'arêtes

| Relation | Label | Poids |
|----------|-------|-------|
| Agent ↔ Agent | "similarité X%" | Score cosinus |
| Agent ↔ Skill | "compatibilité X%" | Score cosinus |
| Agent ↔ Concept | Mot-clé | 0.5 |

### Exemple de réponse API

```json
{
  "nodes": [
    {"id":"agent-architect","label":"architect","type":"agent","color":"#1f6feb","emoji":"🏛️","size":50,
     "data":{"description":"Conception système","keywords":"système, adr, microservices","memory":"Active"}},
    {"id":"skill-github","label":"github","type":"skill","color":"#d29922","emoji":"🧩","size":35,
     "data":{"path":"github","description":"GitHub integration"}},
    {"id":"concept-securite","label":"securite","type":"concept","color":"#bc8cff","emoji":"💡","size":30,
     "data":{"count":"3"}}
  ],
  "edges": [
    {"source":"agent-architect","target":"agent-senior-dev","weight":0.15,"label":"similarité 15%"},
    {"source":"agent-architect","target":"skill-github","weight":0.08,"label":"compatibilité 8%"},
    {"source":"agent-architect","target":"concept-securite","weight":0.5,"label":"securite"}
  ]
}
```

### Fonctionnalités du panneau

- **Recherche** : filtre les nœuds par nom
- **Filtre par type** : Agent, Skill, Concept
- **Panneau latéral** : clic sur un nœud → propriétés + connexions directes
- **Force simulation** : animation continue (répulsion + attraction + gravité)
- **Réinitialiser** : efface la recherche et les filtres

---

## UC-11 — Administration : gestion des utilisateurs

### Description
L'administrateur gère les utilisateurs : création, promotion/rétrogradation,
activation/désactivation, suppression.

### Acteurs
- **Administrateur**

### Flux

```
┌──────────┐  GET /api/users          ┌──────────┐
│  SPA     │ ──────────────────────► │  FastAPI  │
│ (admin)  │ ◄────────────────────── │           │
│          │  [{id,name,role,...}]   │           │
└─────┬────┘                          └──────────┘
      │
      │  Actions disponibles par utilisateur :
      │  - Promouvoir admin / Rétrograder user
      │  - Activer / Désactiver
      │  - Supprimer
      ▼
┌──────────┐  POST /api/admin/user/update   ┌──────────┐
│  SPA     │ ─────────────────────────────► │  FastAPI  │
│          │ ◄───────────────────────────── │           │
│          │  {success:true}                │           │
└──────────┘                                 └──────────┘
```

### Exemple

```bash
# Créer un utilisateur
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/api/admin/user/create \
  -H "Content-Type: application/json" \
  -b "token=e5f6g7h8..." \
  -d '{"name":"Alice Dev","email":"alice@local.home","password":"pass123","role":"user"}'

# Promouvoir admin
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/api/admin/user/update \
  -H "Content-Type: application/json" \
  -b "token=e5f6g7h8..." \
  -d '{"id":2,"role":"admin"}'
```

---

## UC-12 — Administration : permissions par utilisateur

### Description
L'administrateur définit quels panneaux et quels agents sont accessibles à chaque
utilisateur non-admin.

### Acteurs
- **Administrateur**

### Flux

```
┌──────────┐  Clique sur le lien     ┌──────────┐
│  SPA     │  "X panneaux, Y agents" │  Modal   │
│ (admin)  │ ──────────────────────► │  Perms   │
│          │                         │          │
│          │  ☑ overview  ☑ chat     │          │
│          │  ☐ admin    ☑ kanban    │          │
│          │                         │          │
│          │  ☑ architect ☑ devops   │          │
│          │  ☐ senior-dev           │          │
└─────┬────┘                         └─────┬────┘
      │                                    │
      │  Enregistrer                       │
      ▼                                    │
┌──────────┐  POST /api/admin/user/permissions  │
│  SPA     │ ───────────────────────────────────┘
│          │ ◄──── {success:true}
└──────────┘
```

### Exemple

```bash
curl -sk -X POST https://agents-os.apps.okdsnoapps.vmapps.home/api/admin/user/permissions \
  -H "Content-Type: application/json" \
  -b "token=e5f6g7h8..." \
  -d '{
    "id": 2,
    "permissions": {
      "panels": ["overview", "chat", "kanban"],
      "agents": ["architect", "devops"]
    }
  }'
```

### Résultat
L'utilisateur #2 ne verra que les panneaux Dashboard, Chat et Kanban dans sa sidebar.
Il ne pourra discuter qu'avec les agents `architect` et `devops`.

---

## UC-13 — Dashboard : surveillance des métriques

### Description
Le dashboard affiche en temps réel les métriques système : nombre d'appels API,
taux d'erreur, uptime, latence. Un flux d'activité affiche les événements récents.

### Acteurs
- **Utilisateur**

### Flux

```
┌──────────┐  GET /api/status (5s)   ┌──────────┐
│  SPA     │ ──────────────────────► │  FastAPI  │
│ (dash)   │ ◄────────────────────── │           │
│          │  {total_calls, errors,  │           │
│          │   uptime_seconds, ...}  │           │
└──────────┘                         └──────────┘
```

### Widgets

| Widget | Donnée | Format |
|--------|--------|--------|
| Requêtes totales | `total_calls` | Nombre |
| Taux d'erreur | `errors / total_calls` | Pourcentage |
| Uptime | `uptime_seconds` | Xh Ym |
| Latence LLM | `latency_ms` | Graphique temporel |
| Appels par agent | `calls_per_agent` | Graphique barres |
| Flux d'activité | `activityFeed[]` | Liste chronologique |
| Actions rapides | - | Boutons |

---

## Résumé des endpoints par use case

| UC | Endpoint | Méthode | Auth |
|----|----------|---------|------|
| 01 | `/api/signup` | POST | Non |
| 02 | `/api/login` | POST | Non |
| 03 | `/v1/chat/completions` | POST | Token |
| 04 | `/api/admin/agent/create` | POST | Admin |
| 05 | `/api/admin/agent/delete` | POST | Admin |
| 06 | *localStorage* | - | - |
| 07 | `/api/profiles` | GET | Token |
| 08 | `/api/skills` | GET | Token |
| 09 | *localStorage* | - | - |
| 10 | `/api/profiles` + `/api/skills` | GET | Token |
| 11 | `/api/admin/user/*` | POST | Admin |
| 12 | `/api/admin/user/permissions` | POST | Admin |
| 13 | `/api/status` | GET | Token |
