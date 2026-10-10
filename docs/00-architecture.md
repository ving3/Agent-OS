# Architecture — Hermes Agent sur OKD SNO

Cluster : `okdsnoapps.vmapps.home` (OKD 4.22 SNO, 192.168.1.62)
Namespace : `ai`
Date : 2026-10-08

---

## 1. Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                      Navigateur                             │
│                         │ HTTPS                             │
└─────────────────────────┼───────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
   ┌──────────────────┐    ┌──────────────────┐
   │  Route OpenWebUI │    │  Route Hermes    │
   │  openwebui.apps. │    │  hermes.apps.    │
   │  okdsnoapps...   │    │  okdsnoapps...   │
   └────────┬─────────┘    └────────┬─────────┘
            │                       │
   ┌────────▼─────────┐    ┌────────▼─────────┐
   │ Service OpenWebUI│    │ Service Hermes   │
   │     :8080        │    │   :8777 (API)    │
   └────────┬─────────┘    └────────┬─────────┘
            │                       │
            │  API OpenAI-compatible │
            ├──────────────────────►│
            │                       │
            │                 ┌─────▼─────┐
            │                 │  BytePlus │
            │                 │  ARK API  │
            │                 │ (Fournis- │
            │                 │  seur LLM)│
            │                 └───────────┘
            │
   ┌────────▼─────────┐
   │   PostgreSQL     │
   │     :5432        │
   │  (OpenWebUI DB)  │
   └──────────────────┘

   ┌──────────────────┐
   │      Redis       │
   │     :6379        │
   │ (Cache/Sessions) │
   └──────────────────┘
```

## 2. Composants

| Composant | Rôle | Port interne | PVC |
|---|---|---|---|
| **OpenWebUI** | Interface de chat web | 8080 | `openwebui-data` (2Gi) |
| **Hermes Agent** | Agent IA autonome avec API OpenAI-compatible | 8777 (API OpenAI-compatible) | `hermes-data` (10Gi) |
| **PostgreSQL** | Base de données OpenWebUI | 5432 | `postgres-data` (2Gi) |
| **Redis** | Cache et sessions | 6379 | `redis-data` (1Gi) |

## 3. Flux de communication

```
Utilisateur → Navigateur → Route OpenWebUI → Service OpenWebUI
                                                    │
                                                    │ HTTP (OpenAI-compatible)
                                                    ▼
                                          Service Hermes Agent
                                          (API Server :8777)
                                                    │
                                                    │ HTTP (OpenAI-compatible)
                                                    ▼
                                          BytePlus ARK API
                                          (ark.ap-southeast.bytepluses.com)
```

## 4. Stockage persistant

| PVC | Taille | Type | Chemin | Montage conteneur | Contenu |
|---|---|---|---|---|---|
| `hermes-data` | 10Gi | **NFS** (Fedora hôte) | `192.168.1.60:/var/data/hermes` | `/opt/data` | Sessions, skills, mémoire, config Hermes |
| `openwebui-data` | 2Gi | Local (VM) | `/var/lib/ai/openwebui` | `/app/backend/data` | Comptes, conversations OpenWebUI |
| `postgres-data` | 2Gi | Local (VM) | `/var/lib/ai/postgres` | `/var/lib/postgresql/data` | Base OpenWebUI |
| `redis-data` | 1Gi | Local (VM) | `/var/lib/ai/redis` | `/data` | Données Redis |

## 5. Routes OpenShift

| Route | URL | Service | Port | TLS |
|---|---|---|---|---|
| `openwebui` | `https://openwebui.apps.okdsnoapps.vmapps.home` | `openwebui` | 8080 | edge/Redirect |
| `hermes` | `https://hermes.apps.okdsnoapps.vmapps.home` | `hermes` (API) | 8777 | edge/Redirect |
| `hermes-bridge` | `https://hermes-bridge.apps.okdsnoapps.vmapps.home` | `hermes-bridge` | 8686 | edge/Redirect |

## 6. Secrets

| Secret | Clés | Utilisé par |
|---|---|---|
| `ai-secrets` | `BYTEDANCE_API_KEY` | Hermes Agent (fournisseur LLM) |
| `ai-secrets` | `WEBUI_SECRET_KEY` | OpenWebUI (signature sessions) |
| `ai-secrets` | `POSTGRES_PASSWORD` | PostgreSQL + OpenWebUI |
| `ai-secrets` | `REDIS_PASSWORD` | Redis |

## 7. Modèle de déploiement

- **Strategy** : `Recreate` (les PVCs sont en `RWO`, un seul pod par déploiement)
- **SCC** : `anyuid` (Hermes Agent nécessite UID 10000, OpenWebUI UID 0)
- **Resources** : Hermes Agent 1 CPU / 2Gi RAM min, 2 CPU / 4Gi RAM max
- **Image Hermes** : `nousresearch/hermes-agent:latest` (Docker Hub)
- **Image OpenWebUI** : `ghcr.io/open-webui/open-webui:main`
- **Image PostgreSQL** : `postgres:16-alpine`
- **Image Redis** : `redis:7-alpine`
