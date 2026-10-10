# Suivi de Deploiement : Agentic OS — Agent IA Dashboard

Branche : `Hermes_Agents` | Cluster : `okdsnoapps.vmapps.home` (OKD 4.22 SNO)
Derniere mise a jour : 2026-10-10 (Agentic OS Dashboard v2.2)

---

## 1. Resultat

**Deploiement reussi.** Agentic OS Dashboard operationnel avec authentification,
chat agents, canvas, graphe, kanban, memoires, skills et administration.

## 2. Composants actifs

| Composant | Namespace | Statut |
|-----------|-----------|--------|
| Hermes Agent (gateway) | `ai` | Running |
| OpenWebUI | `ai` | Running |
| Agentic OS Dashboard | `ai` | Running |
| PostgreSQL | `ai` | Running |
| Redis | `ai` | Running |

## 3. Architecture

```
Navigateur
    │
    ├── https://openwebui.apps.okdsnoapps.vmapps.home
    │       └── OpenWebUI ──► Hermes API ──► BytePlus ARK
    │
    ├── https://hermes.apps.okdsnoapps.vmapps.home
    │       └── Hermes API (OpenAI-compatible :8777)
    │
    └── https://agents-os.apps.okdsnoapps.vmapps.home
            └── Agentic OS Dashboard (:8686)
                    ├── API Hermes (:8777)
                    └── PVC hermes-data (lecture profils/skills)
```

## 4. Fonctionnalites du Dashboard

| Panneau | Fonction |
|---------|----------|
| **Dashboard** | Cartes agents avec chat rapide |
| **Canvas** | Terminaux simultanes de tous les agents |
| **Graphe** | Visualisation des taches par agent |
| **Chat** | Chat dedie avec selection d'agent |
| **Memoire** | Consultation memoires persistantes |
| **Skills** | Liste des competences disponibles |
| **Kanban** | Gestion de missions (todo/progress/done) |
| **Administration** | Gestion utilisateurs + permissions + creation agents (max 50) + suppression agents |

## 5. Authentification

- Login / Signup (premier inscrit = admin)
- Sessions avec cookies HttpOnly
- Mots de passe hachees (SHA-256)
- Routes protegees (redirection login si non authentifie)

## 6. Stockage

| Volume | Taille | Type | Contenu |
|--------|--------|------|---------|
| hermes-data | 10Gi | NFS (Fedora) | Profils, skills, memoire Hermes |
| openwebui-data | 2Gi | Local (VM) | Comptes, conversations OpenWebUI |
| postgres-data | 2Gi | Local (VM) | Base de donnees OpenWebUI |
| redis-data | 1Gi | Local (VM) | Cache Redis |
de bout en bout :

| Capacité | Statut | Preuve |
|---|---|---|
| Pod Running (uid 1000, non-root) | ✅ | `agents-sandbox-55d67f49d5-xx6th  1/1  Running` |
| API FastAPI `/health` | ✅ | `{"status":"healthy","sandbox":"dynamic","package_manager":"nix"}` |
| Installation de paquet à chaud (sans root, sans restart) | ✅ | `nix-env -iA nixpkgs.ripgrep` → `rg` disponible immédiatement |
| **Persistance sur le PVC à travers un redémarrage de pod** | ✅ | Après suppression du pod : `nix-env -q` → `ripgrep-15.2.0` toujours présent |
| Agent CrewAI → LiteLLM → BytePlus | ✅ | `POST /agent/coder/run` → `BONJOUR_SANDBOX` |
| Agent autonome installe **et** exécute un outil | ✅ | `cowsay` installé puis exécuté par l'agent via ses outils |
| Clone Git authentifié (PAT injecté) | ✅ | `GIT_TOKEN_set: true` dans `/env` |

Paquets Nix installés par les agents et persistés dans le PVC au moment du gel de version :
```
cowsay-3.8.4
jq-1.8.2
nix-2.35.2
ripgrep-15.2.0
tree-2.3.2
```

---

## 2. Tableau de Bord

| # | Étape | Statut |
|---|-------|--------|
| 0 | Tag `main` v0.1 + branche `Docker-Sandbox` | ✅ |
| 1 | Documentation (guide + schéma + journal) | ✅ |
| 2 | Suppression de l'ancien déploiement (namespace `agents-ai`) | ✅ |
| 3 | Ré-application du bundle kustomize | ✅ |
| 4 | Import des images externes dans le registre interne | ✅ |
| 5 | Création du Secret `cloud-api-keys` | ✅ |
| 6 | Création du répertoire PV sur le nœud (`/var/lib/agents-ai/sandbox`) | ✅ |
| 7 | Build de l'image `agents-sandbox` (9 itérations, cf. §4) | ✅ |
| 8 | Déploiement + SCC + binding PV/PVC | ✅ |
| 9 | Vérification fonctionnelle (API, Nix, persistance, LLM) | ✅ |
| 10 | Mise à jour de la documentation | ✅ |
| 11 | Commit, push, tag `v0.1.1` | ✅ |

---

## 3. Commandes de Déploiement (procédure consolidée)

```powershell
$k = "C:\Users\ving\Projets\OKD SNO\openshift-agent-install\playbooks\generated_manifests\okdsnoapps\auth\kubeconfig"
$root = "C:\Users\ving\Projets\Agents IA"
```

### 3.1 Pré-requis nœud : répertoire du PV local

Les PV de type `local` exigent que le répertoire existe **physiquement sur le nœud**.
Sans accès SSH, la méthode fiable est `oc debug node` (monte le FS hôte dans `/host`) :

```powershell
oc --kubeconfig $k debug node/okdsnoapps -- chroot /host bash -c @"
mkdir -p /var/lib/agents-ai/sandbox
chmod 0775 /var/lib/agents-ai/sandbox
chown core:core /var/lib/agents-ai/sandbox
chcon -v --reference=/var/lib/agents-ai/qdrant /var/lib/agents-ai/sandbox
ls -laZ /var/lib/agents-ai/
"@
```

> `core` = uid 1000 sur CoreOS, soit exactement l'uid d'exécution du conteneur.
> Le `chcon --reference` copie le contexte SELinux `container_file_t` des PV voisins.

### 3.2 Build de l'image

```powershell
oc --kubeconfig $k apply -f (Join-Path $root "agents-sandbox\okd-build.yaml") -n agents-ai
oc --kubeconfig $k adm policy add-scc-to-user agents-ai-gpu-hostdev -z gpu-workload -n agents-ai
oc --kubeconfig $k -n agents-ai start-build agents-sandbox `
    --from-dir (Join-Path $root "agents-sandbox") --follow
```

### 3.3 Déploiement

```powershell
oc --kubeconfig $k apply -f (Join-Path $root "deploy\agents-sandbox.yaml") -n agents-ai

# Secret (hors manifeste : voir §4.10)
oc --kubeconfig $k -n agents-ai create secret generic agents-sandbox-keys `
  --from-literal="GIT_TOKEN=<PAT>" `
  --from-literal="LITELLM_API_KEY=<cle_virtuelle_litellm>" `
  --dry-run=client -o yaml | oc --kubeconfig $k apply -f -

oc --kubeconfig $k -n agents-ai rollout restart deployment/agents-sandbox
oc --kubeconfig $k -n agents-ai rollout status deployment/agents-sandbox --timeout=300s
```

### 3.4 Vérification

```powershell
oc --kubeconfig $k -n agents-ai get pods -l app.kubernetes.io/name=agents-sandbox
oc --kubeconfig $k -n agents-ai exec deployment/agents-sandbox -c sandbox -- nix-env -q

# Test fonctionnel complet (installation à chaud)
oc --kubeconfig $k -n agents-ai exec deployment/agents-sandbox -c sandbox -- `
  bash -lc "nix-env -iA nixpkgs.ripgrep && rg --version"
```

---

## 4. Problèmes Rencontrés & Solutions Appliquées

Douze problèmes ont été rencontrés. Ils sont classés par ordre d'apparition, car plusieurs
masquaient le suivant.

### 4.1 `python3-venv` n'existe pas sur Fedora 41 (échec de build)

**Symptôme**
```
Failed to resolve the transaction:
No match for argument: python3-venv
error: build error: building at STEP "RUN dnf -y update && dnf -y install ... python3-venv ..."
```

**Cause** : depuis Fedora 40/41, `python3-venv` n'est plus un paquet séparé ; le module
`venv` est fourni par `python3` (standard).

**Solution** : retirer `python3-venv` de la liste `dnf install` ; ajouter `findutils` et
`tar` (utiles aux outils). `python3 -m venv` fonctionne sans paquet supplémentaire.

---

### 4.2 L'installateur Nix a besoin de créer `/nix` en root (échec de build)

**Symptôme**
```
directory /nix does not exist; creating it by running 'mkdir -m 0755 /nix && chown agent /nix' using sudo
sudo: a terminal is required to read the password
please manually run 'mkdir -m 0755 /nix && chown agent /nix' as root to create /nix
```

**Cause** : Nix s'installe dans `/nix` (racine), mais l'installateur tournait sous
l'utilisateur non-root `agent`, sans `sudo` exploitable en build.

**Solution** : créer `/nix` en tant que root **avant** `USER agent`, puis en donner la
propriété :
```dockerfile
RUN mkdir -m 0755 /nix && chown agent:agent /nix
USER agent
RUN curl -L https://nixos.org/nix/install | sh -s -- --no-daemon
```

---

### 4.3 `nix-channel` introuvable après l'installation (échec de build)

**Symptôme**
```
STEP 13/26: RUN . /home/agent/.nix-profile/etc/profile.d/nix.sh && nix-channel --add ... 
/bin/sh: line 1: nix-channel: command not found
```

**Cause** : en supprimant le bloc `ENV USER/HOME/PATH` j'avais cassé la résolution du
profil Nix ; le script `nix.sh` ajoute `~/.nix-profile/bin` au `PATH`, mais la commande
`nix-channel` vit dans le profil *par défaut*.

**Solution** : expliciter le `PATH` dans la même couche `RUN` :
```dockerfile
RUN export PATH="/home/agent/.nix-profile/bin:/nix/var/nix/profiles/default/bin:$PATH" && \
    nix-channel --add https://nixos.org/channels/nixpkgs-unstable nixpkgs && \
    nix-channel --update && nix-env --version
```

---

### 4.4 SCC `restricted-v2` refuse un uid explicite (pods refusés à la création)

**Symptôme**
```
Error creating: pods "agents-sandbox-..." is forbidden:
unable to validate against any security context constraint:
  provider restricted-v2: .spec.securityContext.fsGroup: Invalid value: [1000]: 1000 is not an allowed group
  provider restricted-v2: .containers[0].runAsUser: Invalid value: 1000: must be in the ranges: [1000800000, 1000809999]
  provider "agents-ai-gpu-hostdev": Forbidden: not usable by user or serviceaccount
```

**Cause** : double. (a) OpenShift `restricted-v2` n'autorise pas d'uid fixe hors plage
allouée ; (b) l'image doit écrire dans `/nix` et `$HOME` avec un uid stable → il faut un
SCC permissif. Le SCC dédié `agents-ai-gpu-hostdev` (`runAsUser: RunAsAny`) existait et
listait bien `system:serviceaccount:agents-ai:gpu-workload`, **mais le RoleBinding
associé n'existait pas** dans le namespace recréé.

**Solution**
1. Utiliser `serviceAccountName: gpu-workload` (le même que qdrant/ollama/postgres).
2. Créer le RoleBinding manquant :
   ```powershell
   oc --kubeconfig $k adm policy add-scc-to-user agents-ai-gpu-hostdev -z gpu-workload -n agents-ai
   # clusterrole.rbac.authorization.k8s.io/system:openshift:scc:agents-ai-gpu-hostdev added: "gpu-workload"
   ```
3. Fixer l'uid applicatif à **1000** (utilisateur `agent` de l'image, propriétaire du PVC).

**Complément** : le manifeste `deploy/gpu-scc.yaml` déclare le SCC avec `users:` mais
`oc apply` ne crée pas le RoleBinding ; d'où l'étape explicite `adm policy`.

---

### 4.5 Le déploiement part dans le namespace `default`

**Symptôme** : `oc get deployment -A -l app.kubernetes.io/name=agents-sandbox` renvoie
`default   agents-sandbox`. Le PVC `agents-sandbox-home` y est créé, et le PV
`agents-ai-sandbox-local` s'y lie : `Bound  default/agents-sandbox-home`.

**Cause** : `oc apply -f deploy/agents-sandbox.yaml` **sans `-n`** utilise le namespace
courant du contexte (`default`). Le fichier ne porte pas de `metadata.namespace`.

**Solution** : toujours passer `-n agents-ai` (le bundle kustomize, lui, force
`namespace: agents-ai`, d'où la différence de comportement entre `apply -k deploy/` et
`apply -f deploy/agents-sandbox.yaml`).

```powershell
foreach ($r in "deployment/agents-sandbox","pvc/agents-sandbox-home","service/agents-sandbox",
               "configmap/agents-sandbox-config","secret/agents-sandbox-keys","serviceaccount/agents-sandbox") {
  oc --kubeconfig $k -n default delete $r --ignore-not-found
}
```

---

### 4.6 PV `Released` impossible à relier à un nouveau PVC

**Symptôme** : après suppression du PVC fautif, le PV reste `Released` avec
`CLAIM: default/agents-sandbox-home`, et le nouveau PVC reste `Pending` indéfiniment.

**Cause** : politique `persistentVolumeReclaimPolicy: Retain`. À la suppression du PVC,
le PV conserve son `claimRef` et ne peut donc pas se lier à un autre PVC.

**Solution** : supprimer **et** recréer le PV. `Retain` garantit que les données sur le
disque (`/var/lib/agents-ai/sandbox`) ne sont pas effacées.

```powershell
oc --kubeconfig $k delete pv agents-ai-sandbox-local
oc --kubeconfig $k -n agents-ai delete pvc agents-sandbox-home
oc --kubeconfig $k apply -f (Join-Path $root "deploy\agents-sandbox.yaml") -n agents-ai
# → PV Bound / agents-ai/agents-sandbox-home, PVC Bound
```

> Note : `oc patch pv ... -p '{"spec":{"claimRef":null}}'` est l'alternative, mais le
> quoting PowerShell du JSON est source d'erreurs ; la recréation est plus fiable.

---

### 4.7 Répertoire du PV inexistant sur le nœud

**Symptôme**
```
Warning  FailedMount  MountVolume.NewMounter initialization failed for volume
"agents-ai-sandbox-local" : path "/var/lib/agents-ai/sandbox" does not exist
```

**Cause** : un PV `local` suppose un répertoire préexistant sur l'hôte. Les autres PV
fonctionnaient car leurs répertoires dataient de l'installation initiale du cluster
(`qdrant`, `ollama`, `postgres`, `open-webui`) ; `sandbox` était le seul manquant.

**Solution** : créer le répertoire sur le nœud via `oc debug node` (cf. §3.1). Le
`chcon --reference` est important : sans contexte SELinux `container_file_t`, le montage
échouerait ou resterait en lecture seule.

---

### 4.8 Le PVC masque l'image : `uvicorn not found in $PATH`

**Symptôme**
```
Warning  Failed  kubelet  Error: container create failed:
executable file `uvicorn` not found in $PATH: No such file or directory
```

**Cause — le piège central de ce déploiement.** Le PVC est monté sur `/home/agent`.
Or tout ce qui avait été construit dans l'image **sous `/home/agent`** (le venv
`/home/agent/.venv`, le code `/home/agent/app`, le profil Nix) est **masqué** par le
montage. Le conteneur ne voyait donc ni `uvicorn` ni le module `app`.

**Solution — séparer état persistant et contenu d'image** :

| Chemin | Emplacement | Rôle |
|---|---|---|
| `/opt/venv` | Image | venv Python (jamais masqué) |
| `/opt/app` | Image | code applicatif (jamais masqué) |
| `/opt/nix-seed.tar.gz` | Image | archive du store Nix initial |
| `/home/agent` | **PVC** | profil Nix, repos, workspace |
| `/nix` | **PVC** (subPath `nix`) | store Nix → paquets à chaud persistants |

Le code a été adapté en conséquence (`config.py` : `VENV_BIN = "/opt/venv/bin"`).

---

### 4.9 Le profil Nix n'est pas dans `/nix/var/nix/profiles`

**Symptôme** : après ensemencement, `nix-env` toujours introuvable. Inspection du tar :
```
nix/var/nix/profiles/
nix/var/nix/profiles/per-user/     <-- vide
```
…et dans les gcroots :
```
nix/var/nix/gcroots/auto/9in0wqv... -> /home/agent/.local/state/nix/profiles/profile-1-link
```

**Cause** : avec Nix ≥ 2.x en installation **mono-utilisateur**, le profil utilisateur
n'est plus `/nix/var/nix/profiles/default` mais
`~/.local/state/nix/profiles/profile` (cible de `~/.nix-profile`). En n'archivant que
`/nix`, on perdait le profil.

**Solution** : archiver **aussi l'état Nix du HOME** dans le seed :
```dockerfile
RUN set -e; \
    PATHS="nix home/agent/.local/state/nix"; \
    for p in home/agent/.nix-profile home/agent/.nix-defexpr home/agent/.nix-channels home/agent/.config/nix; do \
      if [ -e "/$p" ]; then PATHS="$PATHS $p"; fi; \
    done; \
    tar -C / -czf /opt/nix-seed.tar.gz $PATHS
```
et faire monter le PVC **aussi** sur `/home/agent` dans l'initContainer.
Le marqueur a été versionné (`.seeded` → `.seeded-v2`) pour forcer un ré-ensemencement.

**Leçon** : lors d'un changement de contenu du seed, **incrémenter le marqueur**, sinon
l'initContainer saute l'extraction et l'ancien contenu perdure.

---

### 4.10 Le Secret placeholder écrasait les vraies clés à chaque `oc apply`

**Symptôme**
```
litellm.AuthenticationError: ... Received=CHAN****_KEY, expected to start with 'sk-'.
```

**Cause** : `deploy/agents-sandbox.yaml` déclarait le Secret `agents-sandbox-keys` avec
`stringData: {LITELLM_API_KEY: "CHANGE_ME_LITELLM_ORCHESTRATOR_KEY"}`. Chaque
`oc apply` réécrivait donc le Secret et remplaçait la vraie clé par le placeholder.

**Solution** : **retirer le Secret du manifeste**. Il doit être créé une seule fois, hors
du cycle `apply` (par script ou manuellement). Un commentaire explicite a été laissé dans
le YAML à l'emplacement du Secret.

---

### 4.11 Fichiers créés par root → `PermissionError` en uid 1000

**Symptôme**
```
PermissionError: [Errno 13] Permission denied:
'/home/agent/.local/share/crewai/credentials/secret.key'
```

**Cause** : pendant la phase de mise au point, le conteneur a tourné en `runAsUser: 0`
et a créé des fichiers dans le PVC appartenant à root. Après passage à l'uid 1000
(souhaité, pour Nix), ces fichiers sont inaccessibles.

**Solution** : l'initContainer tourne en **root** (il a besoin d'écrire le store) et
corrige systématiquement les propriétés avant de rendre la main :
```bash
chown -R 1000:1000 /home/agent
chown 1000:1000 /nix /nix/.seeded-v2 /nix/var /nix/var/nix
```
Répartition finale : **initContainer root**, **conteneur applicatif uid 1000**.

---

### 4.12 L'allowlist de commandes bloquait l'usage prévu

**Symptôme** : l'agent installait correctement un paquet puis ne pouvait pas l'exécuter :
```
- Paquet installe : tree-2.3.2
- Tentatives d'execution directes : echec (securite : 'tree' non dans les prefixes autorises)
- Methode alternative utilisee : nix-shell -p tree --run "tree --version"
```
L'agent a **contourné** la restriction — preuve que la politique était inadaptée.

**Cause** : `ALLOWED_COMMANDS_PREFIX` était une **allowlist** de préfixes. Or l'intérêt
même de la sandbox est d'exécuter des binaires inconnus à l'avance (`tree`, `ffmpeg`,
`gcc`, …) installés à la volée. Il fallait aussi maintenir la liste en permanence.

**Solution** : passer à une **blocklist** par défaut. On bloque uniquement le
destructeur (sous-chaînes + regex) et on autorise le reste ; l'ancienne allowlist est
réactivable via `SANDBOX_STRICT_ALLOWLIST=true`.

Risque résiduel jugé acceptable : conteneur non-root (uid 1000), sans droit sur l'hôte,
sur un cluster SNO mono-nœud dédié ; les commandes bloquées couvrent l'arrêt du nœud,
l'écriture de périphériques bruts, `rm -rf /`, `chown/chmod -R /`, `mkfs`, `kill 1`.

**Validation après correction** :
```
Commandes lancees : nix_package_manager install cowsay, dynamic_terminal "cowsay -t OK"
Paquets installes : cowsay-3.8.4 ...
Sortie : ASCII art cowsay correcte
```

---

## 5. Incidents connexes (hors sandbox, corrigés au passage)

| Incident | Cause | Solution |
|---|---|---|
| `agents-orchestrator` en `ImagePullBackOff` | Image jamais construite après recréation du namespace | `oc start-build agents-orchestrator --from-dir orchestrator/` |
| `litellm` sans clés d'API | Le pod avait démarré **avant** la création du Secret ; les `secretKeyRef` sont `optional: true`, donc silencieusement vides | `oc rollout restart deployment/litellm` après création du Secret |
| `open-webui` en `CreateContainerConfigError` | `OPEN_WEBUI_LITELLM_KEY` absent de `cloud-api-keys` | Clé virtuelle LiteLLM générée + `oc set data secret/cloud-api-keys` |

> **Leçon générale** : avec des `secretKeyRef ... optional: true`, un pod démarré avant
> la création du Secret tourne avec des variables **vides** sans échouer. Toujours
> redémarrer les consommateurs après création/mise à jour d'un Secret.

---

## 6. État Final (mise a jour 2026-10-07)

### Agents disponibles

| Agent | Endpoint | Modele | Timeout |
|---|---|---|---|
| Orchestrator | `/agent/orchestrator/run` | `deepseek-v4-pro` | 300s |
| Coder | `/agent/coder/run` | `seed-2-0-code` | 180s |
| Reviewer | `/agent/reviewer/run` | `seed-2-0-lite` | 120s |
| Researcher | `/agent/researcher/run` | `deepseek-chat` | 240s |
| **Hermes Communicateur** | `/agent/hermes-communicator/run` | `deepseek-v4-pro` | 120s |
| **Hermes Traducteur** | `/agent/hermes-translator/run` | `glm-5-2` | 90s |
| **Hermes Curateur** | `/agent/hermes-curator/run` | `glm-5-2` | 180s |

### Pods

```powershell
$k = "...\okdsnoapps\auth\kubeconfig"
oc --kubeconfig $k -n agents-ai get pods
```

```
NAME                                   READY   STATUS             
agents-sandbox-55d67f49d5-xx6th        1/1     Running            
crawl4ai-6484fddd68-p9lgs              1/1     Running            
litellm-5ffd894df7-wxzjh               1/1     Running            
ollama-5bfbfc64bd-dmr75                1/1     Running            
postgres-86df7d655-fxpd2               1/1     Running            
qdrant-6fd75dd59c-w8hn6                1/1     Running            
searxng-7dc4659576-9w6gn               1/1     Running            
```

| Ressource | Valeur |
|---|---|
| PVC | `agents-sandbox-home` → `agents-ai-sandbox-local` (20Gi, `Bound`) |
| SCC | `agents-ai-gpu-hostdev` (RoleBinding sur `gpu-workload`) |
| uid conteneur applicatif | 1000 (`agent`) |
| uid initContainer | 0 (root, pour ensemencer le store) |
| Image | `image-registry...:5000/agents-ai/agents-sandbox:latest` (build #9) |
| Clé LLM sandbox | clé virtuelle LiteLLM `sandbox-agents` (droits limités aux 6 modèles) |

---

## 7. Points d'Attention / Dette Technique

1. **Le store Nix sur le PVC croît sans limite.** Aucun `nix-collect-garbage` n'est
   planifié. Pour un usage intensif, prévoir un GC périodique (`nix-collect-garbage -d`)
   ou surveiller l'occupation des 20 Gi.
2. **Coût du premier démarrage.** L'initContainer extrait ~130 Mo (496 Mo décompressés)
   dans le PVC. Les démarrages suivants sont instantanés (marqueur `.seeded-v2`).
3. **Clé virtuelle** : la sandbox utilise une clé virtuelle LiteLLM dédiée
   (`sandbox-agents`), pas la clé maître — à conserver ainsi.
4. **Rotation du PAT GitHub** toujours recommandée (jeton précédemment transmis en clair).
5. **`agents-sandbox.yaml` n'est pas dans le kustomize** au-delà de la ressource :
   le Secret associé est volontairement hors manifeste.

---

## 8. Reproduire le Déploiement

```powershell
$k = "C:\Users\ving\Projets\OKD SNO\openshift-agent-install\playbooks\generated_manifests\okdsnoapps\auth\kubeconfig"
$root = "C:\Users\ving\Projets\Agents IA"

# 1. Répertoire du PV sur le nœud
oc --kubeconfig $k debug node/okdsnoapps -- chroot /host bash -c `
  "mkdir -p /var/lib/agents-ai/sandbox && chmod 0775 /var/lib/agents-ai/sandbox && chown core:core /var/lib/agents-ai/sandbox && chcon --reference=/var/lib/agents-ai/qdrant /var/lib/agents-ai/sandbox"

# 2. Image
oc --kubeconfig $k apply -f (Join-Path $root "agents-sandbox\okd-build.yaml") -n agents-ai
oc --kubeconfig $k adm policy add-scc-to-user agents-ai-gpu-hostdev -z gpu-workload -n agents-ai
oc --kubeconfig $k -n agents-ai start-build agents-sandbox --from-dir (Join-Path $root "agents-sandbox") --follow

# 3. Déploiement
oc --kubeconfig $k apply -f (Join-Path $root "deploy\agents-sandbox.yaml") -n agents-ai
oc --kubeconfig $k -n agents-ai create secret generic agents-sandbox-keys `
  --from-literal="GIT_TOKEN=$(Get-Content "$root\credentials\github-token" -Raw).Trim()" `
  --from-literal="LITELLM_API_KEY=<cle_virtuelle>" `
  --dry-run=client -o yaml | oc --kubeconfig $k apply -f -
oc --kubeconfig $k -n agents-ai rollout restart deployment/agents-sandbox
oc --kubeconfig $k -n agents-ai rollout status deployment/agents-sandbox --timeout=300s

# 4. Vérification
oc --kubeconfig $k -n agents-ai exec deployment/agents-sandbox -c sandbox -- nix-env -q
```
