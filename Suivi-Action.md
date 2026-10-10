# Suivi des Actions — Architecture ArgoCD des Agents AI

> Créé le 2026-10-10 — Audit du déploiement actuel dans le projet `ai` sur `okdsnoapps.vmapps.home`
> Mis à jour le 2026-10-10 — Actions A-01 à A-04, M-01 à M-04 implémentées ✅
> Prochaine étape : déployer la Root App ArgoCD (`argocd/root-app.yaml` → `oc apply -f`)

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

- [x] **A-01** — Structurer le dossier `argocd/` avec l'architecture App of Apps ✅
      - `argocd/root-app.yaml` créé
      - `argocd/apps/` : 6 sous-applications ArgoCD créées
      - `argocd/manifests/` : 6 dossiers de manifests découpés par composant
      - Voir plan détaillé §3

- [x] **A-02** — Convertir le build Binary d'`agents-os` en build Git ✅
      - `argocd/manifests/agents-os/buildconfig.yaml` créé avec `type: Git`
      - Source : `https://github.com/ving3/Agent-OS.git`, contextDir: `agents-os/`
      - Ancien `okd-build.yaml` marqué DEPRECATED

- [x] **A-03** — Sécuriser les secrets pour GitOps ✅
      - `secret-template.yaml` créé avec valeurs CHANGEME (documentation)
      - `ignoreDifferences` configuré dans l'Application `ai-infra` pour les PV
      - Les secrets réels sont appliqués manuellement hors GitOps
      - SealedSecrets : optionnel, à installer si souhaité

- [x] **A-04** — Ajouter le dépôt Git dans ArgoCD ✅
      - `argocd repo add https://github.com/ving3/Agent-OS.git` — Successful
      - Authentification avec token GitHub (ving3)

### 🟡 Priorité Moyenne

- [x] **M-01** — Nettoyer les manifests existants ✅
      - `docs/01-manifests/kustomization.yaml` : marqué DEPRECATED
      - `deploy/agents-os.yaml` : marqué DEPRECATED
      - `agents-os/okd-build.yaml` : marqué DEPRECATED
      - Scripts temporaires supprimés

- [x] **M-02** — Ajouter des NetworkPolicies ✅
      - `allow-dns` : résolution DNS (openshift-dns)
      - `allow-router-ingress` : accès routeur OKD (ports 8080,8686,8777,9119)
      - `allow-intra-namespace` : trafic interne au namespace `ai`
      - `allow-egress-llm` : egress HTTPS Hermes → BytePlus API
      - `allow-egress-registry` : egress agents-os → registry interne

- [x] **M-03** — Ajouter des HealthChecks complets ✅
      - Tous les deployments ont readiness + liveness probes (vérifié)
      - Hermes : startupProbe ajoutée (30s, failureThreshold: 30)
      - Cohérence des timeouts validée

- [x] **M-04** — Taguer les images avec des versions stables ✅
      - `hermes-agent:latest` → `nousresearch/hermes-agent:0.3.14`
      - `postgres:16-alpine` → `postgres:16.6-alpine3.21`
      - `redis:7-alpine` → `redis:7.4.2-alpine3.21`
      - `open-webui:main` → `ghcr.io/open-webui/open-webui:v0.11.4` (déjà tagué)
      - `busybox:1.36` → `busybox:1.37.0`

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
├── root-app.yaml                        ← Application principale (App of Apps)
├── apps/                                ← Applications enfants ArgoCD
│   ├── ai-infra-app.yaml
│   ├── postgres-app.yaml
│   ├── redis-app.yaml
│   ├── hermes-app.yaml
│   ├── openwebui-app.yaml
│   └── agents-os-app.yaml
└── manifests/                           ← Manifests Kubernetes
    ├── ai-infra/
    │   ├── kustomization.yaml
    │   ├── namespace.yaml
    │   ├── persistentvolumes.yaml        ← PV NFS locaux
    │   ├── persistentvolumeclaims.yaml
    │   ├── networkpolicy.yaml            ← 5 NetworkPolicies
    │   ├── serviceaccounts.yaml          ← SA hermes, openwebui, agents-os
    │   └── secret-template.yaml          ← Template (valeurs CHANGEME)
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
    │   ├── route.yaml                    ← hermes + hermes-orchestrator
    │   ├── configmap.yaml
    │   └── hermes-orchestrator-svc.yaml
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
        ├── rbac.yaml                     ← Role + RoleBinding
        ├── buildconfig.yaml              ← Git-based (type: Git)
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
│   ├── okd-build.yaml                  ← ⚠️ DEPRECATED
│   └── app/
│       └── main.py
├── argocd/                             ← ✅ GitOps — Structure complète
│   ├── root-app.yaml
│   ├── apps/                           ← 6 Applications ArgoCD
│   └── manifests/
│       ├── ai-infra/                   ← namespace, PV/PVC, NetworkPolicies, SA
│       ├── postgres/
│       ├── redis/
│       ├── hermes/                     ← + hermes-orchestrator
│       ├── openwebui/
│       └── agents-os/                  ← Build Git + ImageStream + RBAC
├── docs/                               ← ⚠️ DEPRECATED
│   └── 01-manifests/
├── deploy/                             ← ⚠️ DEPRECATED
│   ├── agents-os.yaml
│   └── agents-os-rbac.yaml
├── Suivi-Action.md                     ← Suivi des actions
└── README.md
```

---

## 5. Procédure de déploiement ArgoCD (une fois les manifests prêts)

```bash
# ✅ Étape 1 déjà faite : repo ajouté dans ArgoCD
#    https://github.com/ving3/Agent-OS.git — Successful

# 2. Déployer la Root App (depuis Windows PowerShell avec WSL)
wsl -- oc apply -f /mnt/c/Users/ving/Projets/Agent-OS/argocd/root-app.yaml -n okd-gitops

# 3. Vérifier la synchronisation
wsl -- argocd --grpc-web app list
wsl -- argocd --grpc-web app get hermes-agents-root
wsl -- argocd --grpc-web app get hermes

# 4. Créer le secret ai-secrets (une seule fois, valeurs réelles)
wsl -- bash -c "export KUBECONFIG=/home/ving/okdsnoapps-kubeconfig; oc apply -f /mnt/c/Users/ving/Projets/Agent-OS/docs/01-manifests/01-secrets.yaml -n ai"
```
