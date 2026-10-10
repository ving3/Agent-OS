# Procédure de mise à jour — Hermes Agent + OpenWebUI

---

## 1. Mise à jour de l'image Hermes Agent

### 1.1 Vérifier la version actuelle

```powershell
oc -n ai get deployment hermes -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### 1.2 Mettre à jour

```powershell
# Récupérer la dernière image
oc -n ai import-image nousresearch/hermes-agent:latest --confirm

# Redéployer
oc -n ai rollout restart deployment/hermes
oc -n ai rollout status deployment/hermes --timeout=300s
```

### 1.3 Vérifier après mise à jour

```powershell
oc -n ai logs deployment/hermes --tail=50
oc -n ai get pods -l app.kubernetes.io/name=hermes
```

---

## 2. Mise à jour de l'image OpenWebUI

### 2.1 Mettre à jour

```powershell
oc -n ai import-image ghcr.io/open-webui/open-webui:main --confirm

oc -n ai rollout restart deployment/openwebui
oc -n ai rollout status deployment/openwebui --timeout=300s
```

### 2.2 Vérifier

```powershell
oc -n ai logs deployment/openwebui --tail=30
```

---

## 3. Mise à jour des modèles BytePlus

### 3.1 Modifier le modèle par défaut

Éditer le ConfigMap `hermes-config` :

```powershell
oc -n ai edit configmap hermes-config
```

Modifier la ligne `default:` dans `config.yaml` :

```yaml
model:
  provider: openai
  default: NOUVEAU_MODELE
```

### 3.2 Appliquer la nouvelle config

```powershell
oc -n ai rollout restart deployment/hermes
oc -n ai rollout status deployment/hermes --timeout=300s
```

### 3.3 Mettre à jour OpenWebUI

```powershell
oc -n ai set env deployment/openwebui DEFAULT_MODELS=NOUVEAU_MODELE
```

---

## 4. Mise à jour des clés API

### 4.1 Mettre à jour la clé BytePlus

```powershell
oc -n ai set data secret/ai-secrets --from-literal=BYTEDANCE_API_KEY=NOUVELLE_CLE

# Redémarrer Hermes (lit la clé au démarrage)
oc -n ai rollout restart deployment/hermes
oc -n ai rollout status deployment/hermes --timeout=300s
```

### 4.2 Mettre à jour le mot de passe PostgreSQL

```powershell
$newPassword = "NOUVEAU_MDP"

# Mettre à jour le Secret
oc -n ai set data secret/ai-secrets `
  --from-literal=POSTGRES_PASSWORD=$newPassword `
  --from-literal="DATABASE_URL=postgresql://openwebui:${newPassword}@postgres:5432/openwebui"

# Mettre à jour PostgreSQL
oc -n ai exec deployment/postgres -- sh -c "psql -U openwebui -c \"ALTER USER openwebui PASSWORD '$newPassword';\""

# Redémarrer les consommateurs
oc -n ai rollout restart deployment/postgres
oc -n ai rollout restart deployment/openwebui
```

---

## 5. Mise à jour de la personnalité (SOUL.md)

### 5.1 Modifier le ConfigMap

```powershell
oc -n ai edit configmap hermes-config
```

Modifier la section `SOUL.md`.

### 5.2 Appliquer

```powershell
# Copier la nouvelle config dans le PVC
$hermesPod = oc -n ai get pods -l app.kubernetes.io/name=hermes -o jsonpath='{.items[0].metadata.name}'
oc -n ai exec $hermesPod -- cp /opt/hermes-config/SOUL.md /opt/data/SOUL.md

# Redémarrer
oc -n ai rollout restart deployment/hermes
```

---

## 6. Rollback

### 6.1 Hermes Agent

Si une mise à jour casse le fonctionnement :

```powershell
# Revenir au déploiement précédent
oc -n ai rollout undo deployment/hermes
oc -n ai rollout status deployment/hermes --timeout=300s
```

### 6.2 OpenWebUI

```powershell
oc -n ai rollout undo deployment/openwebui
oc -n ai rollout status deployment/openwebui --timeout=300s
```

### 6.3 Restaurer depuis une sauvegarde

Voir [03-sauvegarde.md](03-sauvegarde.md) §4.

---

## 7. Vérification post-mise à jour

Exécuter ces vérifications après chaque mise à jour :

```powershell
# 1. Tous les pods sont Running
oc -n ai get pods

# 2. Les routes sont accessibles
oc -n ai get routes

# 3. L'API Hermes répond
curl.exe -k https://hermes-ai.apps.okdsnoapps.vmapps.home/health

# 4. OpenWebUI voit les modèles
$webuiKey = oc -n ai get secret ai-secrets -o jsonpath='{.data.WEBUI_SECRET_KEY}' | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }
curl.exe -k https://hermes-ai.apps.okdsnoapps.vmapps.home/v1/models -H "Authorization: Bearer $webuiKey"

# 5. Test de conversation
# Ouvrir OpenWebUI dans le navigateur et envoyer un message test
```
