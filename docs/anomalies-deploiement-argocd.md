# Anomalies, Choix et Solutions — Déploiement ArgoCD Hermes Agents

> Document technique recensant l'ensemble des anomalies rencontrées lors de la migration GitOps
> du projet `ai` sur `okdsnoapps.vmapps.home` vers ArgoCD.
> Date : 2026-10-10

---

## Table des matières

1. [ArgoCD en mode namespaced](#1-argocd-en-mode-namespaced)
2. [Token JWT ArgoCD expiré](#2-token-jwt-argocd-expire)
3. [Tag Hermes agent inexistant](#3-tag-hermes-agent-inexistant)
4. [Conflit value / valueFrom sur le déploiement Hermes](#4-conflit-value--valuefrom-sur-le-deploiement-hermes)
5. [BuildConfig Binary → Git incompatible](#5-buildconfig-binary--git-incompatible)
6. [NetworkPolicies bloquant les builds OpenShift](#6-networkpolicies-bloquant-les-builds-openshift)
7. [contextDir résiduel du build Git](#7-contextdir-residuel-du-build-git)
8. [Quoting PowerShell / WSL pour les commandes oc](#8-quoting-powershell--wsl-pour-les-commandes-oc)
9. [Agents OS hors service après restructuration](#9-agents-os-hors-service-apres-restructuration)
10. [Annexe — Commandes utiles](#10-annexe--commandes-utiles)

---

## 1. ArgoCD en mode namespaced

### Contexte

ArgoCD est déployé via l'opérateur community (`argocd-operator` v0.18.0) dans le namespace
`okd-gitops`. Par défaut, l'opérateur installe ArgoCD en **mode namespaced** : l'Application
Controller ne peut gérer que les ressources dans le namespace où il est installé.

### Symptôme

```text
ComparisonError: Failed to load live state:
  cluster level Namespace "ai" can not be managed when in namespaced mode
```

Puis après correction :

```text
ComparisonError: Failed to load live state:
  namespace "ai" for PersistentVolumeClaim "openwebui-data" is not managed
```

### Choix possibles

| Solution | Description | Complexité |
|----------|-------------|------------|
| **A** — Label `managed-by` | Ajouter `argocd.argoproj.io/managed-by=okd-gitops` sur le namespace cible | Faible |
| **B** — Cluster-wide ArgoCD | Désinstaller et réinstaller ArgoCD avec les droits cluster-admin | Élevée |
| **C** — Namespace RBAC | Créer un RoleBinding dans le namespace `ai` pour le SA argocd | Faible |
| **D** — Ne pas gérer les ressources cluster-level | Retirer Namespace et PersistentVolume des manifests ArgoCD | Faible |

### Solution appliquée (A + C + D)

1. **Label** `argocd.argoproj.io/managed-by=okd-gitops` sur le namespace `ai` :
   ```bash
   oc label namespace ai argocd.argoproj.io/managed-by=okd-gitops --overwrite
   ```

2. **RoleBinding** dans `ai` pour les ServiceAccounts ArgoCD :
   ```bash
   oc apply -f argocd/manifests/ai-infra/argocd-rbac.yaml
   ```
   ```yaml
   # argocd-rbac.yaml
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

3. **Retrait** de `namespace.yaml` et `persistentvolumes.yaml` des manifests ArgoCD
   (ressources cluster-level, déjà créées manuellement).

### Résultat

Les applications ArgoCD gèrent les ressources namespace-scoped (Deployment, Service, Route,
PVC, NetworkPolicy, ServiceAccount, ConfigMap) dans le namespace `ai`.

---

## 2. Token JWT ArgoCD expiré

### Contexte

Le CLI `argocd` utilise un token de session JWT d'une durée de validité d'environ 24 heures.
Après un certain temps d'inactivité, le token expire et les commandes `argocd app sync`
échouent.

### Symptôme

```text
rpc error: code = PermissionDenied desc = permission denied
```

### Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — Re-login | `argocd login` avec le mot de passe admin |
| **B** — Token longue durée | Générer un token API avec `argocd account generate-token` |
| **C** — Refresh automatique | Configurer un cron de refresh du contexte |

### Solution appliquée (A)

Re-login avec le mot de passe admin documenté dans `credentials/argocd-credentials.md` :

```bash
argocd login argocd-server-okd-gitops.apps.okdsnoapps.vmapps.home \
  --username admin --password <password> \
  --insecure --grpc-web --skip-test-tls \
  --name okdsnoapps-vmapps-home
```

### Résultat

Session JWT renouvelée pour 24h. Pour les usages CI/CD, un token API longue durée
pourrait être généré (Solution B).

---

## 3. Tag Hermes agent inexistant

### Contexte

Dans le cadre de l'action **M-04** (pinnage des images à des versions stables), le tag
`nousresearch/hermes-agent:0.3.14` a été spécifié dans le manifest ArgoCD. Ce tag
**n'existe pas** sur Docker Hub.

### Symptôme

```text
ImagePullBackOff
```

Vérification des tags disponibles sur Docker Hub :

```json
{
  "rc.9-v0.21.7-amd64": "Dernier RC pour architecture amd64",
  "rc.9-v0.21.7": "Multi-arch",
  "latest": "Tag inexistant (non publie)"
}
```

Aucun tag `0.3.14` ou `latest` n'existe dans le repository `nousresearch/hermes-agent`.
Les tags sont au format `rc.X-v0.Y.Z-ARCH`.

### Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — Utiliser le dernier RC | `rc.9-v0.21.7-amd64` — tag valide, stable |
| **B** — Revenir à `latest` | Mais `latest` n'existe pas non plus |
| **C** — Image multi-arch | `rc.9-v0.21.7` sans suffixe architecture |

### Solution appliquée (A)

```yaml
# argocd/manifests/hermes/deployment.yaml
image: nousresearch/hermes-agent:rc.9-v0.21.7-amd64
```

### Résultat

Pod Hermes redémarre avec l'image correcte : `1/1 Running`.

### Leçon

Toujours vérifier les tags disponibles avant de spécifier une version :
```bash
curl -s "https://hub.docker.com/v2/repositories/nousresearch/hermes-agent/tags?page_size=30"
```

---

## 4. Conflit value / valueFrom sur le déploiement Hermes

### Contexte

Le déploiement Hermes existant (déployé manuellement) avait la variable d'environnement
`OPENAI_API_KEY` définie avec une `value` en clair (la clé API BytePlus). Le nouveau
manifest ArgoCD utilise `valueFrom` avec un `secretKeyRef`. Lors de la synchronisation,
ArgoCD tente de patcher le déploiement, mais Kubernetes refuse car un champ ne peut pas
avoir à la fois `value` et `valueFrom`.

### Symptôme

```text
error when patching Deployment.apps "hermes" is invalid:
  spec.template.spec.containers[0].env[10].valueFrom:
  Invalid value: "": may not be specified when `value` is not empty
```

### Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — Supprimer le déploiement | `oc delete deploy hermes` puis resync ArgoCD |
| **B** — Modifier le déploiement existant | `oc edit deploy hermes` pour aligner sur le manifest |
| **C** — Ignorer la différence | Configurer ArgoCD pour ignorer ce champ |

### Solution appliquée (A)

```bash
oc delete deploy hermes -n ai
# ArgoCD recrée automatiquement le déploiement avec les bonnes spécifications
```

### Résultat

ArgoCD recrée le déploiement Hermes avec `valueFrom: secretKeyRef` et le pod démarre
correctement.

---

## 5. BuildConfig Binary → Git incompatible

### Contexte

Le BuildConfig d'`agents-os` a été changé de `type: Binary` à `type: Git` dans le cadre
de l'action **A-02**. Or, le dépôt GitHub est **privé** et aucun secret d'authentification
n'a été configuré sur le BuildConfig. De plus, le mode namespaced d'ArgoCD ne permet pas
de gérer les BuildConfig efficacement.

### Symptôme

ArgoCD signale `OutOfSync` sur l'application `agents-os` car le BuildConfig du cluster
(type: Binary) ne correspond pas au manifest (type: Git).

### Choix possibles

| Solution | Description | Complexité |
|----------|-------------|------------|
| **A** — Revenir à Binary + ArgoCD | Laisser le BuildConfig en Binary, build manuel | Faible |
| **B** — Git avec secret | Ajouter un `sourceSecret` au BuildConfig + token GitHub | Moyenne |
| **C** — CI externe | Build via GitHub Actions, push vers le registry OKD | Élevée |

### Solution appliquée (A)

Le BuildConfig est maintenu en **Binary** pour les builds manuels. ArgoCD est en
`OutOfSync` sur ce point mais le déploiement fonctionne avec la dernière image buildée.

```bash
# Build manuel (après modification du code) :
oc start-build agents-os -n ai --from-dir=./agents-os --follow --wait
```

### Résultat

L'application `agents-os` reste `OutOfSync` dans ArgoCD (BuildConfig uniquement).
Le déploiement et l'application sont fonctionnels.

---

## 6. NetworkPolicies bloquant les builds OpenShift

### Contexte

L'action **M-02** a ajouté 5 NetworkPolicies dans le namespace `ai` pour isoler le
trafic réseau. Ces politiques restreignent l'egress : seuls certains pods peuvent
accéder à l'extérieur. Les pods de build OpenShift (créés par `oc start-build`) ne
correspondent à aucun sélecteur de pod existant, et se retrouvent donc bloqués.

### Symptôme

```text
Pulling image python:3.11-slim ...
Trying to pull registry.redhat.io/python:3.11-slim...
  -> dial tcp 98.88.164.131:443: i/o timeout
  -> dial tcp 32.199.33.133:443: i/o timeout
error: GenericBuildFailed
```

Puis, après correction partielle :

```text
Pushing image image-registry.openshift-image-registry.svc:5000/ai/agents-os:latest ...
  -> dial tcp 172.30.184.102:5000: i/o timeout
```

### Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — NP dédiées aux builds | Créer des NetworkPolicies ciblant les pods de build |
| **B** — Egress large | Autoriser tout l'egress depuis le namespace `ai` |
| **C** — Build dans un autre namespace | Déplacer les builds hors du namespace `ai` |

### Solution appliquée (A)

Deux NetworkPolicies ajoutées :

```yaml
# allow-egress-builds — pull images depuis Docker Hub / PyPI
spec:
  podSelector:
    matchExpressions:
      - key: openshift.io/build.name
        operator: Exists
  egress:
    - ports:
        - port: 443; protocol: TCP
        - port: 80;  protocol: TCP

# allow-egress-builds-registry — push vers le registry interne OKD
spec:
  podSelector:
    matchExpressions:
      - key: openshift.io/build.name
        operator: Exists
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: openshift-image-registry
      ports:
        - port: 5000; protocol: TCP
```

### Résultat

Les builds peuvent :
1. Puller les images de base depuis Docker Hub (python:3.11-slim)
2. Pusher l'image finale vers le registry interne OKD

---

## 7. contextDir résiduel du build Git

### Contexte

Le BuildConfig a conservé le champ `spec.source.contextDir: agents-os` provenant de
la configuration Git. Lors d'un build Binary, ce champ est interprété comme un sous-chemin
du répertoire uploadé. Comme le build upload déjà le dossier `agents-os/`, le contexte
devient `agents-os/agents-os/` qui n'existe pas.

### Symptôme

```text
error: provided context directory does not exist: agents-os
```

### Solution appliquée

Suppression du champ `contextDir` du BuildConfig :

```bash
oc patch bc agents-os -n ai --type=json \
  -p '[{"op":"remove","path":"/spec/source/contextDir"}]'
```

### Résultat

Le build Binary fonctionne correctement sans `contextDir`.

---

## 8. Quoting PowerShell / WSL pour les commandes oc

### Contexte

L'exécution de commandes `oc` depuis Windows PowerShell vers WSL Fedora pose des
problèmes récurrents de quoting. PowerShell interprète les caractères `$`, `'`, `"`,
`{`, `}` avant de les passer à `wsl -- bash -c "...".

### Symptômes

```powershell
# Échec :
wsl -- oc patch bc agents-os -n ai --type=json -p '[{"op":"remove","path":"..."}]'
# PowerShell interprète les crochets comme un tableau

# Échec :
wsl -- bash -c "oc get pods -o jsonpath='{.items[0].metadata.name}'"
# Le $ est interprété par PowerShell
```

### Solutions appliquées

Deux approches fiables :

**A — Scripts fichiers** (recommandé) :
```powershell
# Écrire le script dans un fichier .sh, l'exécuter dans WSL
wsl -- bash /mnt/c/Users/ving/.../script.sh
```

**B — Commande simple sans caractères spéciaux** :
```powershell
# OK — pas de caractères PowerShell
wsl -- argocd app list
```

### Règle empirique

Si la commande contient `$`, `'`, `"`, `{`, `}`, `[`, `]`, `(`, `)` — utiliser
un script fichier. Sinon, l'inline fonctionne.

---

## 9. Agents OS hors service après restructuration

### Contexte

La restructuration du code de `agents-os` (passage d'un monolithe `main.py` de 1462
lignes à 21 fichiers modulaires) nécessite un nouveau build pour que les changements
prennent effet.

### Symptôme

Après la restructuration du code, le pod en cours d'exécution utilise toujours
l'ancienne image monolithique. Les nouveaux imports (`from panels.overview import...`)
ne sont pas disponibles.

### Solution

```bash
# 1. Rebuild avec le nouveau code
oc start-build agents-os -n ai --from-dir=./agents-os --follow --wait

# 2. Le déploiement se met à jour automatiquement (ImageChange trigger)
# Nouveau pod avec l'image contenant la structure modulaire
```

### Résultat

Le nouveau pod charge correctement les modules :
```python
from panels.overview import handler as overview  # OK
from panels.skills import handler as skills      # OK
from panels.chat import handler as chat          # OK
from panels.admin import handler as admin_panel  # OK
```

---

## 10. Annexe — Commandes utiles

### Diagnostics ArgoCD

```bash
# Lister toutes les apps
argocd app list

# Forcer une synchronisation
argocd app sync <app-name>

# Voir les détails d'une app (erreurs, ressources)
argocd app get <app-name>

# Voir les logs de sync
argocd app logs <app-name>
```

### Diagnostics builds

```bash
# Lister les builds
oc get builds -n ai

# Voir les logs d'un build
oc logs build/<build-name> -n ai

# Démarrer un build Binary
oc start-build agents-os -n ai --from-dir=./agents-os --follow --wait
```

### Diagnostics pods

```bash
# Voir les pods et leur statut
oc get pods -n ai -o wide

# Voir les logs d'un pod
oc logs <pod-name> -n ai

# Voir l'image utilisée par un déploiement
oc get deploy <name> -n ai -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### NetworkPolicies

```bash
# Lister les NetworkPolicies
oc get networkpolicy -n ai

# Voir les règles détaillées
oc get networkpolicy <name> -n ai -o yaml
```

---

## Résumé des anomalies

| # | Anomalie | Cause | Solution | Impact |
|---|----------|-------|----------|--------|
| 1 | ArgoCD namespaced | Installation par défaut de l'opérateur | Label `managed-by` + RBAC + retrait ressources cluster-level | Bloquant |
| 2 | Token expiré | Session JWT 24h | Re-login avec mot de passe admin | Bloquant |
| 3 | Tag Hermes 0.3.14 inexistant | Tag inventé, pas vérifié sur Docker Hub | Correction vers `rc.9-v0.21.7-amd64` | Bloquant |
| 4 | value + valueFrom conflit | Ancien déploiement vs nouveau manifest | Suppression puis recréation du déploiement | Bloquant |
| 5 | BuildConfig Git incompatible | Repo privé sans secret | Maintien en Binary + OutOfSync assumé | Mineur |
| 6 | NetworkPolicies bloquent builds | Absence de règles pour les pods de build | 2 nouvelles NP `allow-egress-builds*` | Bloquant |
| 7 | contextDir résiduel | Héritage du build Git | Suppression du champ | Bloquant |
| 8 | Quoting PowerShell | Différences de syntaxe entre shells | Scripts fichiers au lieu d'inline | Gênant |
| 9 | Ancienne image agents-os | Code modifié sans rebuild | Nouveau build Binary | Fonctionnel |
