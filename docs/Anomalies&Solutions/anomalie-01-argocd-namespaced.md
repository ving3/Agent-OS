# Anomalie 1 — ArgoCD en mode namespaced

> **Date** : 2026-10-10
> **Contexte** : Déploiement de la Root App ArgoCD (App of Apps) sur le cluster `okdsnoapps.vmapps.home`
> **Impact** : Bloquant

---

## Contexte

ArgoCD est déployé via l'opérateur community (`argocd-operator` v0.18.0) dans le namespace
`okd-gitops`. Par défaut, l'opérateur installe ArgoCD en **mode namespaced** : l'Application
Controller ne peut gérer que les ressources dans le namespace où il est installé.

Lors du déploiement des applications enfants (ai-infra, postgres, redis, etc.) qui ciblent
le namespace `ai`, ArgoCD refuse de créer ou gérer des ressources dans un namespace qu'il
ne "manage" pas.

---

## Symptôme

Première erreur — ressources cluster-level (Namespace, PersistentVolume) :

```text
ComparisonError: Failed to load live state:
  cluster level Namespace "ai" can not be managed when in namespaced mode
```

Après correction partielle — ressources namespace-scoped toujours bloquées :

```text
ComparisonError: Failed to load live state:
  namespace "ai" for PersistentVolumeClaim "openwebui-data" is not managed
```

---

## Choix possibles

| Solution | Description | Complexité | Risque |
|----------|-------------|------------|--------|
| **A** — Label `managed-by` | Ajouter `argocd.argoproj.io/managed-by=okd-gitops` sur le namespace cible | Faible | Aucun |
| **B** — Cluster-wide ArgoCD | Désinstaller et réinstaller ArgoCD avec les droits cluster-admin | Élevée | Interruption de service |
| **C** — Namespace RBAC | Créer un RoleBinding dans le namespace `ai` pour le SA argocd | Faible | Aucun |
| **D** — Retirer ressources cluster-level | Ne pas gérer Namespace et PersistentVolume via ArgoCD | Faible | Gestion manuelle des PV |

---

## Solution appliquée (A + C + D)

### 1. Label du namespace

```bash
oc label namespace ai argocd.argoproj.io/managed-by=okd-gitops --overwrite
```

### 2. RoleBinding pour les ServiceAccounts ArgoCD

Fichier : `argocd/manifests/ai-infra/argocd-rbac.yaml`

```bash
oc apply -f argocd/manifests/ai-infra/argocd-rbac.yaml
```

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: argocd-manager
  namespace: ai
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: admin
subjects:
  - kind: ServiceAccount
    name: argocd-argocd-application-controller
    namespace: okd-gitops
  - kind: ServiceAccount
    name: argocd-argocd-server
    namespace: okd-gitops
```

### 3. Retrait des ressources cluster-level des manifests ArgoCD

- `namespace.yaml` retiré de `argocd/manifests/ai-infra/kustomization.yaml`
- `persistentvolumes.yaml` retiré de `argocd/manifests/ai-infra/kustomization.yaml`
- Ces ressources existent déjà sur le cluster et sont gérées manuellement

---

## Résultat

Les applications ArgoCD gèrent les ressources namespace-scoped (Deployment, Service, Route,
PVC, NetworkPolicy, ServiceAccount, ConfigMap) dans le namespace `ai`. Le mode namespaced
n'est plus un blocage.

---

## Fichiers concernés

- `argocd/manifests/ai-infra/argocd-rbac.yaml`
- `argocd/manifests/ai-infra/kustomization.yaml`

## Références

- [Documentation ArgoCD — Managing namespaces](https://argo-cd.readthedocs.io/en/stable/user-guide/namespaces/)
- [Documentation argocd-operator — Namespaced mode](https://argocd-operator.readthedocs.io/)
