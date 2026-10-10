# Hermes Agent + OpenWebUI sur OKD — Livrables

Cluster cible : `okdsnoapps.vmapps.home` | Namespace : `ai`

---

## Documents

| Fichier | Contenu |
|---|---|
| [00-architecture.md](00-architecture.md) | Architecture détaillée, flux, composants |
| [01-manifests/](01-manifests/) | Manifests Kubernetes YAML (kustomize) |
| [02-installation.md](02-installation.md) | Procédure d'installation complète |
| [03-sauvegarde.md](03-sauvegarde.md) | Procédure de sauvegarde et restauration |
| [05-correspondance-repertoires.md](05-correspondance-repertoires.md) | Correspondance Fedora / VM / Conteneur |

## Manifests

| Fichier | Ressources |
|---|---|
| `00-namespace.yaml` | Namespace `ai` |
| `01-secrets.yaml` | Secret `ai-secrets` (BytePlus, PostgreSQL, Redis, WebUI) |
| `02-persistentvolumes.yaml` | 4 PVs locaux (hermes 10Gi, openwebui 2Gi, postgres 2Gi, redis 1Gi) |
| `03-persistentvolumeclaims.yaml` | 4 PVCs |
| `04-postgres.yaml` | PostgreSQL Deployment + Service |
| `05-redis.yaml` | Redis Deployment + Service |
| `06-hermes-agent.yaml` | Hermes Agent Deployment + Service + Route + ConfigMap |
| `07-openwebui.yaml` | OpenWebUI Deployment + Service + Route |
| `08-serviceaccounts.yaml` | ServiceAccounts `hermes` + `openwebui` + `agents-os` |

## Agentic OS Dashboard

Le dashboard Agentic OS est deploye separement via :
- `agents-os/app/main.py` — application Python (HTTPServer)
- `agents-os/Dockerfile` — image Docker
- `agents-os/okd-build.yaml` — BuildConfig OKD
- `deploy/agents-os.yaml` — Deployment + Service + Route

### Fonctionnalites

| Panneau | Description |
|---|---|
| **Dashboard** | Cartes agents avec chat rapide |
| **Canvas** | Terminaux simultanes de tous les agents |
| **Graphe** | Visualisation des taches par agent |
| **Chat** | Chat dedie avec selection d'agent |
| **Memoire** | Consultation memoires persistantes |
| **Skills** | Liste des competences disponibles |
| **Kanban** | Gestion de missions (todo/progress/done) |
| **Administration** | Gestion utilisateurs, permissions, creation/suppression agents (max 50) |

### Authentification

- Login `/login` et Signup `/signup`
- Premier inscrit = administrateur
- Sessions avec cookies HttpOnly
- Routes protegees (redirection si non authentifie)
- Admin panel integre au dashboard (`/admin` ou bouton sidebar)
- Permissions par panneaux et agents (cases a cocher)
- Creation d'agents depuis le panel Chat Agent (bouton "+ Creer un agent")
| `kustomization.yaml` | Bundle Kustomize |

## URLs

| Service | URL |
|---|---|
| OpenWebUI | `https://openwebui.apps.okdsnoapps.vmapps.home` |
| Hermes API | `https://hermes.apps.okdsnoapps.vmapps.home/v1/models` (clé : WEBUI_SECRET_KEY) |
| Hermes API (interne) | `http://hermes:8777/v1` |

## Déploiement rapide

```powershell
$manifests = "C:\Users\ving\Projets\Agents IA\Documentations\Hermes_Agents\01-manifests"

# 1. Répertoires hôtes
oc debug node/okdsnoapps -- chroot /host bash -c "mkdir -p /var/lib/ai/{hermes,openwebui,postgres,redis} && chown core:core /var/lib/ai/{hermes,openwebui,postgres,redis} && chcon -t container_file_t /var/lib/ai/{hermes,openwebui,postgres,redis}"

# 2. Créer le Secret avec les vraies clés (NE PAS utiliser 01-secrets.yaml)
$webuiKey = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
$pgPwd = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})
$redisPwd = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})
oc -n ai create secret generic ai-secrets `
  --from-literal=BYTEDANCE_API_KEY=ark-... `
  --from-literal=WEBUI_SECRET_KEY=$webuiKey `
  --from-literal=POSTGRES_PASSWORD=$pgPwd `
  --from-literal=REDIS_PASSWORD=$redisPwd `
  --from-literal="DATABASE_URL=postgresql://openwebui:${pgPwd}@postgres:5432/openwebui"

# 3. Déployer
oc apply -f $manifests\00-namespace.yaml
oc apply -f $manifests\02-persistentvolumes.yaml
oc apply -f $manifests\03-persistentvolumeclaims.yaml
oc apply -f $manifests\04-postgres.yaml
oc apply -f $manifests\05-redis.yaml
oc apply -f $manifests\06-hermes-agent.yaml
oc apply -f $manifests\07-openwebui.yaml
oc apply -f $manifests\08-serviceaccounts.yaml

# 4. SCC
oc adm policy add-scc-to-user anyuid -z hermes -n ai
oc adm policy add-scc-to-user anyuid -z openwebui -n ai

# 5. Attendre
oc -n ai rollout status deployment/postgres --timeout=120s
oc -n ai rollout status deployment/redis --timeout=120s
oc -n ai rollout status deployment/hermes --timeout=300s
oc -n ai rollout status deployment/openwebui --timeout=300s
```

## Créer des agents spécialisés (profils)

Après déploiement, se connecter au pod Hermes :

```powershell
oc -n ai exec -it deployment/hermes -- bash
```

Créer un profil spécialisé :

```bash
hermes profile create devops
hermes profile use devops
# Personnaliser le SOUL.md, les outils, etc.
```

Voir [02-installation.md](02-installation.md) §6.3 pour les détails.
