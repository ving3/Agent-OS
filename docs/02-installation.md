# ⚠️ DEPRECATED — Voir docs/00-architecture-v3.md et Suivi-Action.md

# Procédure d'installation — Hermes Agent + OpenWebUI sur OKD

Cluster : `okdsnoapps.vmapps.home` (OKD 4.22 SNO) | Namespace : `ai`
Version déployée : 2026-10-08

---

## 1. Prérequis

- Accès administrateur au cluster (`kubeadmin`)
- `oc` CLI connecté au cluster
- Clé API BytePlus ARK (Coding Plan) : format `ark-...`
- Accès SSH ou `oc debug node` au nœud `okdsnoapps`

### 1.1 Connexion au cluster

```powershell
oc login --server=https://api.okdsnoapps.vmapps.home:6443 `
  -u kubeadmin -p "MOT_DE_PASSE_KUBEADMIN" `
  --insecure-skip-tls-verify=true
```

---

## 2. Création des répertoires hôtes (PVs locaux)

Les PVs sont de type `local`. Les répertoires doivent exister sur le nœud SNO.

```powershell
oc debug node/okdsnoapps -- chroot /host bash -c "
mkdir -p /var/lib/ai/{hermes,openwebui,postgres,redis}
chown core:core /var/lib/ai/{hermes,openwebui,postgres,redis}
chcon -t container_file_t /var/lib/ai/{hermes,openwebui,postgres,redis}
chmod 0775 /var/lib/ai/{hermes,openwebui,postgres,redis}
ls -laZ /var/lib/ai/
"
```

> `core` = uid 1000 sur CoreOS. Le contexte SELinux `container_file_t` est requis
> pour que les conteneurs puissent écrire dans ces répertoires.

---

## 3. Configuration des secrets

Ne pas utiliser le fichier `01-secrets.yaml` directement (il contient des
placeholders). Créer le Secret avec `oc create secret` :

```powershell
# Générer des mots de passe aléatoires
$webuiKey = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 48 | ForEach-Object {[char]$_})
$pgPassword = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})
$redisPassword = -join ((48..57)+(65..90)+(97..122) | Get-Random -Count 24 | ForEach-Object {[char]$_})

# Créer le Secret
oc -n ai create secret generic ai-secrets `
  --from-literal=BYTEDANCE_API_KEY=ark-votre-cle-ici `
  --from-literal=WEBUI_SECRET_KEY=$webuiKey `
  --from-literal=POSTGRES_PASSWORD=$pgPassword `
  --from-literal=REDIS_PASSWORD=$redisPassword `
  --from-literal="DATABASE_URL=postgresql://openwebui:${pgPassword}@postgres:5432/openwebui"
```

| Clé | Description |
|---|---|
| `BYTEDANCE_API_KEY` | Clé API BytePlus ARK (format `ark-...`) |
| `WEBUI_SECRET_KEY` | Chaîne aléatoire ≥ 32 caractères (signature sessions) |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL |
| `REDIS_PASSWORD` | Mot de passe Redis |
| `DATABASE_URL` | URL de connexion PostgreSQL pour OpenWebUI |

---

## 4. Déploiement

### 4.1 Namespace et PVs/PVCs

```powershell
$manifests = "C:\Users\ving\Projets\Agents IA\Documentations\Hermes_Agents\01-manifests"

oc apply -f $manifests\00-namespace.yaml
oc apply -f $manifests\02-persistentvolumes.yaml
oc apply -f $manifests\03-persistentvolumeclaims.yaml
```

### 4.2 Services (PostgreSQL, Redis, Hermes Agent, OpenWebUI)

```powershell
oc apply -f $manifests\04-postgres.yaml
oc apply -f $manifests\05-redis.yaml
oc apply -f $manifests\06-hermes-agent.yaml
oc apply -f $manifests\07-openwebui.yaml
oc apply -f $manifests\08-serviceaccounts.yaml
```

### 4.3 Lier les SCC

Hermes Agent utilise s6-overlay (PID 1) et nécessite `runAsUser: 0`.
OpenWebUI utilise PostgreSQL et nécessite le SCC `anyuid`.

```powershell
oc adm policy add-scc-to-user anyuid -z hermes -n ai
oc adm policy add-scc-to-user anyuid -z openwebui -n ai
```

### 4.4 Attendre le déploiement

```powershell
oc -n ai rollout status deployment/postgres --timeout=120s
oc -n ai rollout status deployment/redis --timeout=120s
oc -n ai rollout status deployment/hermes --timeout=300s
oc -n ai rollout status deployment/openwebui --timeout=300s
```

---

## 5. Validation

### 5.1 Vérifier les pods

```powershell
oc -n ai get pods
```

Résultat attendu :
```
NAME                         READY   STATUS    RESTARTS   AGE
hermes-xxxxxxxxxx-xxxxx      1/1     Running   0          2m
openwebui-xxxxxxxxxx-xxxxx   1/1     Running   0          2m
postgres-xxxxxxxxxx-xxxxx    1/1     Running   0          2m
redis-xxxxxxxxxx-xxxxx       1/1     Running   0          2m
```

### 5.2 Vérifier les routes

```powershell
oc -n ai get routes
```

Résultat attendu :
```
NAME            HOST/PORT                                       SERVICES        PORT
hermes          hermes.apps.okdsnoapps.vmapps.home               hermes          api
hermes-bridge   hermes-bridge.apps.okdsnoapps.vmapps.home        hermes-bridge   bridge
openwebui       openwebui.apps.okdsnoapps.vmapps.home            openwebui       http
```

### 5.3 Vérifier l'API Hermes

```powershell
$webuiKey = oc -n ai get secret ai-secrets -o jsonpath='{.data.WEBUI_SECRET_KEY}' | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

curl.exe -k https://hermes.apps.okdsnoapps.vmapps.home/v1/models `
  -H "Authorization: Bearer $webuiKey"
```

Résultat attendu : liste JSON contenant le modèle `hermes-agent`.

### 5.4 Vérifier OpenWebUI

```powershell
curl.exe -k -s -o /dev/null -w "%{http_code}" https://openwebui.apps.okdsnoapps.vmapps.home/
# Réponse : 200
```

Ouvrir `https://openwebui.apps.okdsnoapps.vmapps.home` dans un navigateur.
Le premier compte créé devient administrateur.

### 5.5 Vérifier la communication OpenWebUI → Hermes

1. Dans OpenWebUI, créer le compte admin (**Sign up**).
2. Démarrer un **New Chat**.
3. Le modèle `hermes-agent` doit apparaître dans le sélecteur.
4. Envoyer : `Bonjour, présente-toi.`
5. Hermes répond via BytePlus ARK.

---

## 6. Configuration post-installation

### 6.1 Créer le compte admin OpenWebUI

1. Ouvrir `https://openwebui.apps.okdsnoapps.vmapps.home`
2. Cliquer sur **Sign up**
3. Renseigner nom, email, mot de passe
4. Ce compte est automatiquement administrateur

### 6.2 Configurer Hermes Agent

Se connecter au pod Hermes :

```powershell
oc -n ai exec -it deployment/hermes -- bash
```

Puis dans le conteneur :
```bash
hermes model              # Choisir le modèle par défaut
hermes skills list        # Lister les skills disponibles
hermes skills install <nom>  # Installer un skill
```

### 6.3 Créer des agents spécialisés (profils)

Hermes permet de créer des profils (agents spécialisés) avec leur propre
personnalité, leurs propres outils et leur propre mémoire.

#### Profil DevOps

```bash
# Dans le pod Hermes
hermes profile create devops
hermes profile use devops

# Configurer la personnalité
# Le SOUL.md est créé automatiquement. Pour le modifier :
cat > /opt/data/profiles/devops/SOUL.md << 'EOF'
# Agent DevOps - Personnalite

Tu es un agent DevOps specialise, expert en infrastructure et operations.
Tu aides les utilisateurs avec le deploiement, la gestion de conteneurs,
l'orchestration Kubernetes, l'administration systeme et l'automatisation CI/CD.

- Tu es pragmatique, oriente resultats et operationnel.
- Tu privilegies la securite et la fiabilite dans toutes tes actions.
- Tu documentes tes interventions (commandes executees, modifications).
- Tu proposes des solutions idempotentes et reproductibles.
- Tu verifies l'etat du systeme avant et apres chaque modification.
- Tu reponds en francais sauf demande contraire.

## Domaines d'expertise
- Docker & conteneurisation (docker, docker-compose)
- Kubernetes (kubectl, helm, kustomize)
- SSH & administration distante
- CI/CD (pipelines, GitHub Actions, GitLab CI)
- Infrastructure as Code (Terraform, Ansible)
- Monitoring & logging (Prometheus, Grafana, ELK)
EOF

# Activer les outils specifiques
hermes tools enable terminal file search git

# Le profil est pret
hermes profile list    # Lister tous les profils
hermes profile use devops   # Basculer sur ce profil
```

#### Autres profils possibles

| Profil | Usage | Outils recommandés |
|---|---|---|
| `architecte` | Conception technique, plans | `terminal file search` |
| `reviewer` | Revue de code, sécurité | `terminal file search git` |
| `data-science` | Analyse de données, ML | `terminal file search python` |
| `sysadmin` | Administration système | `terminal file ssh` |

### 6.4 Utiliser un profil depuis OpenWebUI

1. Dans OpenWebUI, démarrer un **New Chat**.
2. Sélectionner le modèle `hermes-agent`.
3. Envoyer : `Utilise le profil devops pour analyser ce deploiement Kubernetes : ...`
4. Hermes bascule automatiquement sur le profil demandé.

Ou en ligne de commande dans le pod :
```bash
hermes --profile devops chat -q "Analyse l'etat du cluster"
```

---

## 7. Résolution des problèmes

### Le pod Hermes ne démarre pas (CrashLoopBackOff)

```powershell
oc -n ai logs deployment/hermes --tail=100
oc -n ai describe pod -l app.kubernetes.io/name=hermes
```

Causes fréquentes :
- **s6-overlay** : erreur `/run` permissions → vérifier `runAsUser: 0`
- `BYTEDANCE_API_KEY` invalide → vérifier le Secret
- Image `nousresearch/hermes-agent:latest` non disponible → vérifier l'accès Internet du nœud
- PVC non monté → vérifier les répertoires hôtes (§2)

### OpenWebUI n'affiche aucun modèle

```powershell
# Tester l'API Hermes depuis le pod OpenWebUI
$pod = oc -n ai get pods -l app.kubernetes.io/name=openwebui -o jsonpath='{.items[0].metadata.name}'
oc -n ai exec $pod -- curl -s http://hermes:8777/v1/models
```

### Route inaccessible (certificat)

Les Routes utilisent TLS edge avec le certificat auto-signé du cluster.
Dans le navigateur : accepter l'avertissement de sécurité.

### OpenWebUI ne démarre pas (PostgreSQL)

```powershell
oc -n ai logs deployment/openwebui --tail=50
```

Vérifier que `DATABASE_URL` dans le Secret est correct :
```
postgresql://openwebui:<MDP>@postgres:5432/openwebui
```
