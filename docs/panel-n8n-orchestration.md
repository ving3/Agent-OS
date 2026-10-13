# Panel n8n Orchestration — Documentation détaillée

> **Date** : 2026-10-13
> **Version** : Agent OS 3.0 · n8n 2.43.4
> **Fichiers** : `agents-os/backend/routers/n8n.py`, `agents-os/frontend/src/components/n8n.ts`

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture](#2-architecture)
3. [Interface du panel](#3-interface-du-panel)
4. [Backend : endpoints API](#4-backend--endpoints-api)
5. [Modes d'orchestration](#5-modes-dorchestration)
6. [Guide d'utilisation](#6-guide-dutilisation)
7. [Créer un workflow n8n qui pilote les agents](#7-créer-un-workflow-n8n-qui-pilote-les-agents)
8. [Déploiement et configuration](#8-déploiement-et-configuration)
9. [Dépannage](#9-dépannage)

---

## 1. Vue d'ensemble

Le panel **⚡ n8n Orchestration** permet de piloter les agents IA depuis l'interface
Agent OS selon deux approches complémentaires :

| Approche | Description | Quand l'utiliser |
|----------|-------------|------------------|
| **Orchestration séquentielle** | Chaîne d'agents exécutée par le backend : chaque agent reçoit la mission + les réponses des agents précédents | Tests rapides, chaînes simples |
| **Workflows n8n** | Automatisation complète dans n8n (conditions, boucles, appels externes…) déclenchée depuis le panel | Pipelines complexes, planification |

Le panel offre aussi la visibilité sur les workflows n8n existants et leurs exécutions.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Agent OS (agents-os)                          │
│                                                                      │
│  ┌──────────────┐   fetch /api/n8n/*    ┌───────────────────────┐   │
│  │  Panel n8n   │ ────────────────────► │  FastAPI (routers/n8n) │   │
│  │  (n8n.ts)    │ ◄──────────────────── │                       │   │
│  └──────────────┘                      └──────┬────────────┬─────┘   │
│                                               │            │          │
│                                  httpx +       │            │ httpx    │
│                        X-N8N-API-KEY           │            │          │
│                                               ▼            ▼          │
│                              ┌─────────────────────┐  ┌────────────┐ │
│                              │  n8n (n8n:5678)     │  │   Hermes   │ │
│                              │  workflows          │  │  (8777)    │ │
│                              │  executions         │  │  agents IA │ │
│                              │  webhooks           │  │            │ │
│                              └──────────┬──────────┘  └────────────┘ │
│                                         │ HTTP Request nodes          │
│                                         ▼                             │
│                                   DeepSeek API (externe)               │
└─────────────────────────────────────────────────────────────────────┘
```

### Composants

| Composant | Rôle | Localisation |
|-----------|------|--------------|
| `components/n8n.ts` | UI du panel (workflows, orchestration, résultats) | `agents-os/frontend/src/` |
| `routers/n8n.py` | API REST du panel + proxy n8n | `agents-os/backend/` |
| n8n 2.43.4 | Moteur d'automatisation | Pod `n8n` (namespace `ai`) |
| Hermes | Gateway LLM des agents | Pod `hermes` (namespace `ai`) |
| `ai-secrets` | Secret `N8N_API_KEY` + `N8N_ENCRYPTION_KEY` | Secret OpenShift |

### Déploiement n8n

| Ressource | Valeur |
|-----------|--------|
| Image | `n8nio/n8n:latest` (2.43.4) |
| Route | https://n8n.apps.okdsnoapps.vmapps.home |
| Stockage | PVC `n8n-data` (5Gi, `ai-local`) → `/home/node/.n8n` |
| UID | UID aléatoire OpenShift + `fsGroup: 1000740000` (plage SCC de la namespace) |
| Auth API | Clé API publique (`X-N8N-API-KEY`), audience `public-api` |

---

## 3. Interface du panel

Le panel est accessible depuis la sidebar : **⚡ n8n Orchestration** (entre Kanban et Admin).

### 3.1 En-tête

```
⚡ Orchestration n8n    [● n8n en ligne]    [Ouvrir n8n ↗]
```

- **Statut** : pastille verte « n8n en ligne » ou rouge « n8n hors ligne »
  (requête `GET /api/n8n/status` à chaque affichage et au clic sur Rafraîchir)
- **Ouvrir n8n ↗** : ouvre l'éditeur n8n dans un nouvel onglet

### 3.2 Colonne gauche — Workflows

**Carte « Workflows »** :
- Liste des workflows n8n avec :
  - Nom
  - Badge `actif` (vert) / `inactif` (gris)
  - Bouton **▶** : exécute le workflow (`POST /api/n8n/trigger`)
  - Bouton **📜** : affiche les exécutions du workflow
- Bouton **🔄 Rafraîchir** : recharge la liste + le statut

**Carte « Exécutions récentes »** :
- 20 dernières exécutions du workflow sélectionné
- Badge de statut : `success` (vert), `error` (rouge), autre (bleu)
- Horodatage localisé (`new Date(started_at).toLocaleString("fr")`)

### 3.3 Colonne droite — Orchestration

**Carte « 🔗 Orchestrer une chaîne d'agents »** :
- **Agents** : chips cochables (les 2 premiers sont pré-cochés par défaut).
  L'ordre de coche = ordre d'exécution. Le bouton **+ Agent** coche tout.
- **Mission** : textarea multi-lignes
- Bouton **▶ Orchestrer** : lance l'exécution (désactivé pendant l'exécution)

**Carte « Résultats »** :
- Un bloc par agent : nom en bleu + réponse tronquée à 600 caractères

---

## 4. Backend : endpoints API

Tous les endpoints exigent un token de session Agent OS (cookie `token`).

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/n8n/status` | GET | `{"online": true/false}` — sonde `/healthz` de n8n |
| `/api/n8n/workflows` | GET | Liste des workflows (`id, name, active, created_at, updated_at`) |
| `/api/n8n/workflows/{id}/executions` | GET | 20 dernières exécutions (`id, workflow_id, status, started_at, stopped_at`) |
| `/api/n8n/trigger` | POST | Exécute un workflow (`{workflow_id, payload}`) |
| `/api/n8n/orchestrate` | POST | Orchestration (voir §5) |

### Détail des appels n8n sous-jacents

Le proxy backend utilise `httpx` vers `http://n8n:5678` avec le header
`X-N8N-API-KEY` (valeur lue dans le secret `ai-secrets` → `N8N_API_KEY`).

| Endpoint Agent OS | Appel n8n effectué |
|-------------------|--------------------|
| `/api/n8n/workflows` | `GET /api/v1/workflows` |
| `/api/n8n/workflows/{id}/executions` | `GET /api/v1/executions?limit=20&workflowId={id}` |
| `/api/n8n/trigger` | `POST /api/v1/workflows/{id}/run` |

En cas d'échec réseau n8n, les réponses sont dégradées proprement :
`{"workflows": [], "online": false}` — le panel affiche « n8n hors ligne ».

---

## 5. Modes d'orchestration

### 5.1 Mode séquentiel (par défaut)

Requête :

```json
POST /api/n8n/orchestrate
{
  "agents": ["devops", "architect"],
  "message": "Planifie l'automatisation des déploiements"
}
```

Algorithme :

```
contexte = message
pour chaque agent :
    réponse = call_hermes_api(agent, [user: contexte])
    résultats += {agent, réponse}
    si réponse commence par "[Erreur]" → stop
    contexte = contexte + "\n\n[Réponse de <agent>]\n" + réponse[:2000]
```

- Chaque agent reçoit le **contexte cumulatif** (mission + réponses précédentes tronquées à 2000 caractères)
- L'appel à Hermes passe par `call_hermes_api` (endpoint `/v1/chat/completions` du gateway Hermes)
- En cas d'erreur d'un agent, la chaîne s'arrête et l'erreur est visible dans les résultats

### 5.2 Mode workflow n8n

Requête :

```json
POST /api/n8n/orchestrate
{
  "workflow_id": "a1b2c3...",
  "agents": ["devops", "architect"],
  "message": "…"
}
```

Le backend déclenche `POST /api/v1/workflows/{id}/run` avec le payload
`{agents, message}`. C'est le **workflow n8n** qui orchestre (branches
conditionnelles, appels externes, planification, etc.).

---

## 6. Guide d'utilisation

### 6.1 Orchestrer une chaîne d'agents (30 secondes)

1. Ouvrir le panel **⚡ n8n Orchestration**
2. Cocher les agents dans l'ordre souhaité (ex. `architect` puis `senior-dev` puis `code-reviewer`)
3. Saisir la mission : « Concevoir puis implémenter un endpoint d'authentification »
4. Cliquer **▶ Orchestrer**
5. Lire les résultats : chaque bloc montre la réponse de l'agent, et chaque
   agent a reçu le contexte des réponses précédentes

### 6.2 Exécuter un workflow n8n

1. Vérifier que le statut est « n8n en ligne »
2. Dans la carte Workflows, cliquer **▶** sur le workflow
3. Le message « Workflow déclenché ! » confirme l'exécution
4. Cliquer **📜** pour voir les exécutions

---

## 7. Créer un workflow n8n qui pilote les agents

Depuis l'éditeur n8n (https://n8n.apps.okdsnoapps.vmapps.home) :

### 7.1 Appeler un agent (Hermes API)

Ajouter un nœud **HTTP Request** :

```yaml
Méthode : POST
URL : http://hermes:8777/v1/chat/completions
Headers :
  Content-Type: application/json
  Authorization: Bearer <WEBUI_SECRET_KEY>
Body (JSON) :
  {
    "model": "hermes-agent",
    "messages": [{"role": "user", "content": "={{ $json.message }}"}]
  }
```

> `WEBUI_SECRET_KEY` est dans le secret `ai-secrets` (utilisée comme clé du
> gateway API Hermes — c'est la valeur de `API_SERVER_KEY` du pod Hermes).

### 7.2 Exemple de workflow « Chaîne de code review »

```
[Webhook] → [HTTP Request: architect] → [HTTP Request: senior-dev]
         → [HTTP Request: code-reviewer] → [Respond to Webhook]
```

Chaque nœud HTTP Request enchaîne sur le contenu du précédent via les
expressions n8n (`{{ $('NodeName').json.choices[0].message.content }}`).

### 7.3 Déclencher le workflow depuis le panel

Le workflow doit être **enregistré** (et idéalement activé pour les
déclencheurs planifiés). Le bouton ▶ du panel appelle l'API n8n
`/api/v1/workflows/{id}/run` — aucun nœud Webhook n'est nécessaire pour
le déclenchement manuel.

---

## 8. Déploiement et configuration

### 8.1 Manifests

| Fichier | Rôle |
|---------|------|
| `argocd/manifests/n8n/deployment.yaml` | Pod n8n (image, env, PVC, probes, fsGroup) |
| `argocd/manifests/n8n/service.yaml` | Service interne `n8n:5678` |
| `argocd/manifests/n8n/route.yaml` | Route `n8n.apps.okdsnoapps.vmapps.home` |
| `argocd/apps/n8n-app.yaml` | Application ArgoCD (auto-sync) |
| `argocd/manifests/ai-infra/persistentvolumes.yaml` | PV `ai-n8n-local` (5Gi, `/var/lib/ai/n8n`) |
| `argocd/manifests/ai-infra/persistentvolumeclaims.yaml` | PVC `n8n-data` |
| `argocd/manifests/ai-infra/networkpolicy.yaml` | `allow-egress-n8n` (HTTPS externes) |

### 8.2 Secrets (cluster)

| Clé | Usage |
|-----|-------|
| `N8N_ENCRYPTION_KEY` | Chiffrement des credentials n8n |
| `N8N_API_KEY` | Clé API publique n8n (header `X-N8N-API-KEY`) — utilisée par le proxy backend |

### 8.3 Variables d'environnement du pod agents-os

| Variable | Valeur |
|----------|--------|
| `N8N_URL` | `http://n8n:5678` |
| `N8N_API_KEY` | depuis le secret `ai-secrets` |

### 8.4 Particularités n8n 2.43 sur OpenShift

- **UID aléatoire** : `HOME=/home/node` + `N8N_USER_FOLDER` explicites
  (sinon `os.homedir()` = `/` → `EACCES /.n8n`)
- **fsGroup** : `1000740000` (plage `openshift.io/sa.scc.supplemental-groups` de la namespace `ai` ; `1000` est refusé par la SCC `restricted-v2`)
- **Auth API** : le basic auth (`N8N_BASIC_AUTH_*`) est ignoré en n8n 2.x.
  La clé API publique doit avoir :
  - `audience = "public-api"` (tiret, pas camelCase)
  - `scopes` = liste complète des scopes granulaires (200 scopes)
  - la clé est stockée **en clair** dans `user_api_keys.apiKey`

---

## 9. Dépannage

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| « n8n hors ligne » dans le panel | Pod n8n down ou NetworkPolicy | `oc get pods -n ai -l app.kubernetes.io/name=n8n` ; vérifier `allow-egress-n8n` |
| 401 sur l'API n8n | Clé API absente/incorrecte | Vérifier `N8N_API_KEY` dans `ai-secrets` et la ligne `user_api_keys` en DB |
| 403 Forbidden | Scopes insuffisants sur la clé | Attribuer tous les scopes (`SELECT slug FROM scope`) |
| `EACCES /.n8n` au démarrage | HOME non défini (UID aléatoire) | Vérifier `HOME=/home/node` + `N8N_USER_FOLDER` |
| Pod refusé par SCC | fsGroup hors plage | Utiliser `1000740000` (plage de la namespace `ai`) |
| Workflow « inactif » | Le workflow n'est pas activé dans n8n | Activer le workflow dans l'éditeur n8n |
| Exécutions vides | Aucun run récent | Cliquer ▶ puis 📜 pour rafraîchir |

---

## Résumé des flux

```
Séquentiel :   Panel → FastAPI → Hermes (agent 1) → Hermes (agent 2) → … → Résultats
Workflow :     Panel → FastAPI → n8n /run → workflow (nœuds HTTP Request → Hermes)
Visibilité :   Panel → FastAPI → n8n /api/v1/* (workflows + exécutions)
```
