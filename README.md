# Agentic OS

Dashboard de gestion d'agents IA avec authentification, chat, canvas, graphe, kanban et administration.

Déployé sur OKD SNO — [Documentation complète](docs/)

## Fonctionnalités

| Panneau | Description |
|---|---|
| **Dashboard** | Cartes agents avec chat rapide |
| **Canvas** | Terminaux simultanés de tous les agents |
| **Graphe** | Visualisation des tâches par agent |
| **Chat** | Chat dédié avec sélection et création d'agents |
| **Mémoire** | Consultation des mémoires persistantes |
| **Skills** | Liste des compétences disponibles |
| **Kanban** | Gestion de missions (todo/progress/done) |
| **Administration** | Gestion utilisateurs, permissions, création/suppression agents |

## Architecture

```
Navigateur ──► Agentic OS Dashboard (:8686)
                   │
                   ├──► API Hermes (:8777)
                   │
                   ├──► SQLite (utilisateurs, sessions)
                   │
                   └──► PVC hermes-data (profils, skills, mémoire)
```

## Déploiement rapide

```bash
# 1. Namespace
kubectl create namespace ai

# 2. Secrets
kubectl -n ai create secret generic ai-secrets \
  --from-literal=BYTEDANCE_API_KEY=ark-... \
  --from-literal=WEBUI_SECRET_KEY=$(openssl rand -hex 24)

# 3. Déploiement
kubectl apply -f deploy/agents-os-rbac.yaml
kubectl apply -f deploy/agents-os.yaml
```

## Authentification

- Login `/login` et Signup `/signup`
- Premier inscrit = administrateur
- Permissions par panneaux et agents (cases à cocher)
- Création d'agents depuis le panel Chat (max 50)

## Stack

- **Backend** : Python HTTPServer
- **Frontend** : Vanilla JS (aucune dépendance)
- **Base** : SQLite
- **Container** : python:3.11-slim + kubectl
- **Orchestration** : OKD / Kubernetes

## Licence

MIT
