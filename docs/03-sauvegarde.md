# Procédure de sauvegarde — Hermes Agent + OpenWebUI

---

## 1. Éléments à sauvegarder

| Élément | Emplacement | Contenu critique |
|---|---|---|
| Données Hermes | PVC `hermes-data` (10Gi) | Sessions, skills, mémoire, config |
| Données OpenWebUI | PVC `openwebui-data` (2Gi) | Comptes utilisateurs, conversations |
| Base PostgreSQL | PVC `postgres-data` (2Gi) | Base OpenWebUI |
| Données Redis | PVC `redis-data` (1Gi) | Cache (optionnel, peut être régénéré) |
| Secrets | Secret `ai-secrets` | Clés API, mots de passe |
| Config Hermes | ConfigMap `hermes-config` | Configuration YAML, SOUL.md |

---

## 2. Sauvegarde à chaud (recommandée)

### 2.1 Sauvegarde PostgreSQL (dump SQL)

```powershell
$backupDir = "C:\Backups\Hermes_Agents\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
New-Item -ItemType Directory -Path $backupDir -Force

$pgPassword = oc -n ai get secret ai-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}' | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

oc -n ai exec deployment/postgres -- sh -c "PGPASSWORD='$pgPassword' pg_dump -U openwebui openwebui" > "$backupDir\openwebui-db.sql"
```

### 2.2 Sauvegarde des fichiers Hermes et OpenWebUI

```powershell
$hermesPod = oc -n ai get pods -l app.kubernetes.io/name=hermes -o jsonpath='{.items[0].metadata.name}'
$webuiPod = oc -n ai get pods -l app.kubernetes.io/name=openwebui -o jsonpath='{.items[0].metadata.name}'

# Sauvegarde Hermes (config, skills, sessions, memoire)
oc -n ai exec $hermesPod -- tar -czf /tmp/hermes-backup.tar.gz -C /opt/data .
oc -n ai cp $hermesPod:/tmp/hermes-backup.tar.gz "$backupDir\hermes-backup.tar.gz"

# Sauvegarde OpenWebUI (comptes, conversations, uploads)
oc -n ai exec $webuiPod -- tar -czf /tmp/openwebui-backup.tar.gz -C /app/backend/data .
oc -n ai cp $webuiPod:/tmp/openwebui-backup.tar.gz "$backupDir\openwebui-backup.tar.gz"
```

### 2.3 Sauvegarde des ressources Kubernetes

```powershell
# Secrets
oc -n ai get secret ai-secrets -o yaml > "$backupDir\secret-ai-secrets.yaml"

# ConfigMap Hermes
oc -n ai get configmap hermes-config -o yaml > "$backupDir\configmap-hermes-config.yaml"

# Tous les manifests appliques
oc -n ai get all,pvc,route,secret,configmap -o yaml > "$backupDir\full-namespace.yaml"
```

---

## 3. Sauvegarde complète (arrêt des services)

### 3.1 Arrêter les déploiements

```powershell
oc -n ai scale deployment/hermes --replicas=0
oc -n ai scale deployment/openwebui --replicas=0
```

### 3.2 Sauvegarder les répertoires hôtes

```powershell
oc debug node/okdsnoapps -- chroot /host bash -c "
backup_dir=/var/lib/ai-backup-\$(date +%Y%m%d_%H%M%S)
mkdir -p \$backup_dir
cp -a /var/lib/ai/hermes \$backup_dir/
cp -a /var/lib/ai/openwebui \$backup_dir/
cp -a /var/lib/ai/postgres \$backup_dir/
cp -a /var/lib/ai/redis \$backup_dir/
tar -czf \$backup_dir.tar.gz -C /var/lib \$backup_dir
echo \"Backup cree : \$backup_dir.tar.gz\"
"
```

### 3.3 Redémarrer les services

```powershell
oc -n ai scale deployment/hermes --replicas=1
oc -n ai scale deployment/openwebui --replicas=1
oc -n ai rollout status deployment/hermes --timeout=300s
oc -n ai rollout status deployment/openwebui --timeout=300s
```

---

## 4. Restauration

### 4.1 Restaurer PostgreSQL

```powershell
$backupSql = "C:\Backups\Hermes_Agents\20261008_120000\openwebui-db.sql"
$pgPassword = oc -n ai get secret ai-secrets -o jsonpath='{.data.POSTGRES_PASSWORD}' | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

Get-Content $backupSql -Raw | oc -n ai exec -i deployment/postgres -- sh -c "PGPASSWORD='$pgPassword' psql -U openwebui openwebui"
```

### 4.2 Restaurer les fichiers Hermes

```powershell
$hermesPod = oc -n ai get pods -l app.kubernetes.io/name=hermes -o jsonpath='{.items[0].metadata.name}'

oc -n ai cp "C:\Backups\Hermes_Agents\20261008_120000\hermes-backup.tar.gz" $hermesPod:/tmp/hermes-backup.tar.gz
oc -n ai exec $hermesPod -- tar -xzf /tmp/hermes-backup.tar.gz -C /opt/data
oc -n ai exec $hermesPod -- rm /tmp/hermes-backup.tar.gz
```

### 4.3 Restaurer OpenWebUI

```powershell
$webuiPod = oc -n ai get pods -l app.kubernetes.io/name=openwebui -o jsonpath='{.items[0].metadata.name}'

oc -n ai cp "C:\Backups\Hermes_Agents\20261008_120000\openwebui-backup.tar.gz" $webuiPod:/tmp/openwebui-backup.tar.gz
oc -n ai exec $webuiPod -- tar -xzf /tmp/openwebui-backup.tar.gz -C /app/backend/data
oc -n ai exec $webuiPod -- rm /tmp/openwebui-backup.tar.gz
```

### 4.4 Redémarrer après restauration

```powershell
oc -n ai rollout restart deployment/hermes
oc -n ai rollout restart deployment/openwebui
```

---

## 5. Automatisation (CronJob Kubernetes)

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: hermes-backup
  namespace: ai
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: backup
              image: bitnami/kubectl:latest
              command:
                - sh
                - -c
                - |
                  kubectl exec deployment/postgres -- sh -c "PGPASSWORD='$POSTGRES_PASSWORD' pg_dump -U openwebui openwebui" > /backups/openwebui-$(date +%Y%m%d).sql
                  echo "Backup termine"
              env:
                - name: POSTGRES_PASSWORD
                  valueFrom:
                    secretKeyRef:
                      name: ai-secrets
                      key: POSTGRES_PASSWORD
          restartPolicy: OnFailure
```

---

## 6. Fréquence recommandée

| Élément | Fréquence | Rétention |
|---|---|---|
| Base PostgreSQL | Quotidienne | 7 jours |
| Données Hermes | Quotidienne | 7 jours |
| Données OpenWebUI | Hebdomadaire | 4 semaines |
| Secrets/Config | À chaque modification | Permanent |
