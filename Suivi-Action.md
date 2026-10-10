# Suivi des Actions — Architecture ArgoCD des Agents AI

> Créé le 2026-10-10 — Audit du déploiement actuel dans le projet `ai` sur `okdsnoapps.vmapps.home`

---

## 1. État des lieux

### Déploiement actuel (projet `ai`)

| Composant | Image | Statut |
|-----------|-------|--------|
| Hermes Agent | `nousresearch/hermes-agent:latest` | ✅ Running |
| Open WebUI | `ghcr.io/open-webui/open-webui:v0.11.4` | ✅ Running |
| Agentic OS (Dashboard) | Build local `image-registry:5000/ai/agents-os:latest` | ✅ Running |
| PostgreSQL | `postgres:16-alpine` | ✅ Running |
| Redis | `redis:7-alpine` | ✅ Running |

### ArgoCD

| Point | Statut |
|-------|--------|
| ArgoCD installé (namespace `okd-gitops`) | ✅ 4 pods Running |
| Aucune Application configurée | ❌ Liste vide |
| Contexte CLI `okdsnoapps-vmapps-home` | ✅ Login admin OK |

### Constats

- Les manifests existent dans `docs/01-manifests/` et `deploy/` mais ne sont **pas synchronisés** avec le cluster
- Le déploiement a été fait manuellement via `oc apply -f`
- Le build d'`agents-os` est de type **Binary** (`oc start-build`) — incompatible avec ArgoCD
- Les secrets sont en clair dans les manifests YAML
- Pas de GitOps → pas de traçabilité, pas de rollback simple

---

## 2. Actions à réaliser

### 🔴 Priorité Haute

- [ ] **A-01** — Structurer le dossier `argocd/` avec l'architecture App of Apps
      - Créer `argocd/root-app.yaml` (Application racine)
      - Créer `argocd/apps/` (6 sous-applications ArgoCD)
      - Créer `argocd/manifests/` avec les manifests découpés par composant
      - Voir plan détaillé §3

- [ ] **A-02** — Convertir le build Binary d'`agents-os` en build Git
      - Modifier `agents-os/okd-build.yaml` ou créer `argocd/manifests/agents-os/buildconfig.yaml`
      - Source : `https://github.com/ving3/Agent-OS.git`
      - Context dir : `agents-os/`
      - Dockerfile : `agents-os/Dockerfile`
      - Remplacer `type: Binary` par `type: Git`

- [ ] **A-03** — Sécuriser les secrets pour GitOps
      - Installer `SealedSecrets` (bitnami/sealed-secrets) dans le cluster
      - OU `ExternalSecrets` avec un backend vault
      - OU au minimum : séparer les secrets templates des valeurs réelles
      - Les secrets ne doivent **jamais** être commités en clair

- [ ] **A-04** — Ajouter le dépôt Git dans ArgoCD
      - Ajouter le token GitHub dans ArgoCD (`argocd repo add`)
      - Vérifier que le CLI argocd a accès au repo

### 🟡 Priorité Moyenne

- [ ] **M-01** — Nettoyer les manifests existants
      - Supprimer ou déprécier `docs/01-manifests/` (sera remplacé par `argocd/manifests/`)
      - Supprimer ou déprécier `deploy/agents-os.yaml` (remplacé par structure ArgoCD)
      - Supprimer les scripts temporaires de test (`analyze-*.sh`, `setup-*.sh`, etc.)

- [ ] **M-02** — Ajouter des NetworkPolicies
      - Isoler le namespace `ai` : interdire les accès depuis d'autres namespaces
      - Autoriser uniquement les flux internes (hermes → postgres/redis, openwebui → hermes, agents-os → hermes)

- [ ] **M-03** — Ajouter des HealthChecks complets
      - Vérifier que tous les deploiements ont readiness + liveness probes
      - Hermes a déjà des probes (startup 30s, readiness 60s, liveness 120s)
      - Vérifier la cohérence des timeouts

- [ ] **M-04** — Taguer les images avec des versions stables
      - Remplacer `hermes-agent:latest` par `hermes-agent:<version>` explicite
      - Remplacer `postgres:16-alpine` par `postgres:16.6-alpine` (pin exact)
      - Idem pour redis, openwebui

### 🟢 Priorité Basse

- [ ] **B-01** — Ajouter un dashboard Grafana pour le monitoring
      - Métriques Hermes (nombre d'appels, latence, erreurs)
      - Métriques OpenWebUI
      - Métriques ArgoCD

- [ ] **B-02** — Configurer les notifications ArgoCD
      - Webhook Mattermost/Slack pour les syncs
      - Alertes sur échec de déploiement

- [ ] **B-03** — Ajouter des quotas de ressources au namespace `ai`
      - ResourceQuota CPU/Memory
      - LimitRange par défaut

- [ ] **B-04** — Automatiser le build agents-os dans une CI (GitHub Actions)
      - Build et push de l'image dans le registry interne OKD
      - OU push vers un registry externe (Docker Hub, ghcr.io)
      - Mettre à jour automatiquement le manifest dans git

---

## 3. Plan détaillé — Structure ArgoCD App of Apps

```
argocd/                                  ← Racine ArgoCD
├── root-app.yaml                        ← Application principale (auto-déploie les enfants)
└── manifests/                           ← Manifests Kubernetes
    ├── ai-infra/
    │   ├── kustomization.yaml
    │   ├── namespace.yaml
    │   ├── persistentvolumes.yaml        ← PV NFS locaux
    │   ├── persistentvolumeclaims.yaml
    │   └── networkpolicy.yaml
    ├── postgres/
    │   ├── kustomization.yaml
    │   ├── deployment.yaml
    │   └── service.yaml
    ├── redis/
    │   ├── kustomization.yaml
    │   ├── deployment.yaml
    │   └── service.yaml
    ├── hermes/
    │   ├── kustomization.yaml
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   ├── route.yaml
    │   └── configmap.yaml
    ├── openwebui/
    │   ├── kustomization.yaml
    │   ├── deployment.yaml
    │   ├── service.yaml
    │   └── route.yaml
    └── agents-os/
        ├── kustomization.yaml
        ├── deployment.yaml
        ├── service.yaml
        ├── route.yaml
        ├── rbac.yaml
        ├── buildconfig.yaml            ← Git-based (Dockerfile dans agents-os/)
        └── imagestream.yaml
```

### Dépendances entre les Applications

```
ai-infra (namespace + volumes)
    ↓
postgres ──┐
redis ─────┤
           ├── hermes ──── openwebui
           └── agents-os (build → deploy)
```

### Configuration ArgoCD recommandée

```yaml
# root-app.yaml (principe)
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: hermes-agents
  namespace: okd-gitops
spec:
  project: default
  source:
    repoURL: https://github.com/ving3/Agent-OS.git
    path: argocd/manifests/ai-infra
    targetRevision: main
  destination:
    server: https://kubernetes.default.svc
    namespace: ai
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

Chaque sous-application suit le même modèle avec son propre `path`.

---

## 4. Arborescence finale attendue du dépôt

```
Agent-OS/
├── .gitignore
├── credentials/                        ← Ignoré (secrets)
├── agents-os/                          ← Source + Dockerfile
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── okd-build.yaml                  ← À déprécier
│   └── app/
│       └── main.py
├── argocd/                             ← NOUVEAU — Structure GitOps
│   ├── root-app.yaml
│   └── manifests/
│       ├── ai-infra/
│       ├── postgres/
│       ├── redis/
│       ├── hermes/
│       ├── openwebui/
│       └── agents-os/
├── docs/                               ← À déprécier ou archiver
│   └── 01-manifests/
├── deploy/                             ← À déprécier
│   ├── agents-os.yaml
│   └── agents-os-rbac.yaml
├── Suivi-Action.md                     ← Ce fichier
└── README.md
```

---

## 5. Procédure de déploiement ArgoCD (une fois les manifests prêts)

```bash
# 1. Ajouter le repo dans ArgoCD
argocd repo add https://github.com/ving3/Agent-OS.git \
  --username ving3 \
  --password <github-token> \
  --insecure-skip-tls-verify

# 2. Déployer la Root App
oc apply -f argocd/root-app.yaml -n okd-gitops

# 3. Vérifier la synchronisation
argocd --grpc-web app list
argocd --grpc-web app get hermes-agents
argocd --grpc-web app get hermes
```
