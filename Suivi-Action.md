# Suivi des Actions — Architecture ArgoCD des Agents AI

> Créé le 2026-10-10 — Audit du déploiement actuel dans le projet `ai` sur `okdsnoapps.vmapps.home`
> Mis à jour le 2026-10-10 — Actions A-01 à A-04, M-01 à M-04 implémentées ✅
> **✅ Déploiement ArgoCD actif** — Root App + 6 applications enfants déployées et synchronisées
> Prochaine étape : actions B-01 à B-04 (basse priorité)

---

## 1. État des lieux

### Déploiement actuel (projet `ai`)

| Composant | Image | Statut | Géré par ArgoCD |
|-----------|-------|--------|-----------------|
| Hermes Agent | `nousresearch/hermes-agent:rc.9-v0.21.7-amd64` | ✅ Running | ✅ ai-infra, hermes |
| Open WebUI | `ghcr.io/open-webui/open-webui:v0.11.4` | ✅ Running | ✅ openwebui |
| Agentic OS (Dashboard) | `image-registry:5000/ai/agents-os:latest` (build #13) | ✅ Running | ✅ agents-os |
| PostgreSQL | `postgres:16.6-alpine3.21` | ✅ Running | ✅ postgres |
| Redis | `redis:7.4.2-alpine3.21` | ✅ Running | ✅ redis |

### ArgoCD — État après déploiement

| Point | Statut |
|-------|--------|
| ArgoCD installé (namespace `okd-gitops`) | ✅ 4 pods Running |
| Root App `hermes-agents-root` | ✅ Synced — Healthy |
| `ai-infra` (PVC, SA, NetworkPolicies) | ✅ Synced — Healthy |
| `postgres` | ✅ Synced — Healthy |
| `redis` | ✅ Synced — Healthy |
| `hermes` | ✅ Synced — Healthy |
| `openwebui` | ✅ Synced — Healthy |
| `agents-os` | ⚠️ OutOfSync — Healthy (BuildConfig modifié Binary→Git, build à déclencher) |
| NetworkPolicies | ✅ 5 règles actives |
| Dépôt GitHub ajouté | ✅ `argocd repo list` — Successful |
| Contexte CLI `okdsnoapps-vmapps-home` | ✅ Login admin OK |

### Constats (après migration GitOps)

- ✅ Les 6 applications ArgoCD sont déployées et synchronisées
- ✅ Les images sont pinnées à des versions stables
- ✅ Les NetworkPolicies isolent le namespace `ai`
- ✅ Les anciens manifests sont marqués DEPRECATED
- ⚠️ `agents-os` en OutOfSync : le BuildConfig Git-based est créé mais aucun build n'a encore été déclenché (déploiement fonctionne avec l'image du dernier build Binary #13)
- ⚠️ Secrets gérés hors GitOps (appliqués manuellement, `ignoreDifferences` non configuré car pas dans les manifests ArgoCD)

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
      - `hermes-agent:latest` → `nousresearch/hermes-agent:rc.9-v0.21.7-amd64`
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
    │   ├── persistentvolumeclaims.yaml
    │   ├── networkpolicy.yaml            ← 5 NetworkPolicies
    │   ├── serviceaccounts.yaml          ← SA hermes, openwebui, agents-os
    │   ├── secret-template.yaml          ← Template (valeurs CHANGEME)
    │   └── argocd-rbac.yaml             ← Bootstrap (appliqué manuellement)
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

## 5. Procédure de déploiement ArgoCD (déjà exécutée)

### Résumé des opérations réalisées le 2026-10-10

```bash
# 1. Ajouter le repo GitHub dans ArgoCD
argocd repo add https://github.com/ving3/Agent-OS.git \
  --username ving3 --password <token> --insecure

# 2. Créer le RBAC pour ArgoCD dans le namespace ai
oc apply -f argocd/manifests/ai-infra/argocd-rbac.yaml

# 3. Labeler le namespace ai pour ArgoCD (mode namespaced)
oc label namespace ai argocd.argoproj.io/managed-by=okd-gitops --overwrite

# 4. Déployer la Root App (crée les 6 apps enfants)
oc apply -f argocd/root-app.yaml -n okd-gitops

# 5. Synchroniser toutes les apps (hermes a nécessité 2 tentatives :
#    tag 0.3.14 inexistant → corrigé en rc.9-v0.21.7-amd64)
argocd app sync ai-infra postgres redis hermes openwebui agents-os

# 6. Re-créer les déploiements conflictuels (hermes + agents-os)
oc delete deploy hermes -n ai
oc delete deploy agents-os -n ai
# → ArgoCD les recrée automatiquement avec les bonnes spécifications
```

### Problèmes rencontrés et résolutions

| Problème | Cause | Résolution |
|----------|-------|------------|
| `Namespace not managed` | ArgoCD en mode namespaced | Label `argocd.argoproj.io/managed-by=okd-gitops` sur le namespace `ai` |
| `Permission denied` | Token JWT ArgoCD expiré | `argocd login` avec mot de passe admin |
| `env[10] value/valueFrom conflict` | Ancien déploiement avec `value:` en dur vs manifest avec `valueFrom:` secret | `oc delete deploy hermes` puis resync ArgoCD |
| `ImagePullBackOff` hermes | Tag `0.3.14` inexistant | Changé pour `rc.9-v0.21.7-amd64` |
| `agents-os OutOfSync` | BuildConfig changé Binary→Git | Fonctionnel avec l'ancienne image, build Git à déclencher |

### Pour déclencher un build Git agents-os

```bash
# Déclencher un build depuis le repo GitHub
oc start-build agents-os -n ai

# Vérifier le build
oc get builds -n ai -w
```
