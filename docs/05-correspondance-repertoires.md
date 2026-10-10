# Correspondance des répertoires — Hermes Agent sur OKD

Architecture : PC Fedora Hôte → VM okdsnoapps (OKD SNO) → Conteneur Hermes Agent

```
PC Fedora (192.168.1.60)
│
├── /var/data/hermes/          ← NFS exporté vers la VM
│       │
│       ▼  NFS (monté dans le pod)
│
└── Conteneur Hermes (/opt/data)
```

---

## 1. Tableau de correspondance

| PC Fedora (hôte) | okdsnoapps (VM/nœud) | Conteneur Hermes | PVC |
|---|---|---|---|
| `/var/data/hermes` | *(NFS mount dans le pod)* | `/opt/data` | `hermes-data` (NFS) |
| *(N/A)* | `/var/lib/ai/openwebui` | `/app/backend/data` | `openwebui-data` (local) |
| *(N/A)* | `/var/lib/ai/postgres` | `/var/lib/postgresql/data` | `postgres-data` (local) |
| *(N/A)* | `/var/lib/ai/redis` | `/data` | `redis-data` (local) |

---

## 2. Arborescence détaillée

### 2.1 Hermes Agent — `/var/data/hermes` (Fedora) ↔ `/opt/data` (conteneur)

```
PC Fedora                    Conteneur Hermes
/var/data/hermes/           /opt/data/
│                           │
├── config.yaml             ├── config.yaml
├── SOUL.md                 ├── SOUL.md
├── .env                    ├── .env
│                           │
├── profiles/               ├── profiles/          ← Agents spécialisés
│   └── devops/             │   └── devops/
│       ├── config.yaml     │       ├── config.yaml
│       ├── SOUL.md         │       ├── SOUL.md
│       ├── profile.yaml    │       ├── profile.yaml
│       ├── skills/         │       ├── skills/
│       ├── cron/           │       ├── cron/
│       └── backups/        │       └── backups/
│                           │
├── skills/                 ├── skills/            ← Skills globaux
├── sessions/               ├── sessions/          ← Conversations
├── memory/                 ├── memory/            ← Mémoire persistante
│                           │
├── state.db                ├── state.db           ← Base SQLite état
├── kanban.db               ├── kanban.db          ← Base kanban
├── response_store.db       ├── response_store.db
├── shared-state.db         ├── shared-state.db
│                           │
├── logs/                   ├── logs/              ← Journaux
├── cache/                  ├── cache/             ← Cache modèles
├── installs/               ├── installs/          ← Dépendances
│                           │
├── platforms/              ├── platforms/         ← Config messagerie
├── plugins/                ├── plugins/           ← Plugins
├── cron/                   ├── cron/              ← Tâches planifiées
│                           │
└── gateway_state.json      └── gateway_state.json ← État passerelle
```

### 2.2 OpenWebUI — `/var/lib/ai/openwebui` (VM) ↔ `/app/backend/data` (conteneur)

```
okdsnoapps (VM)             Conteneur OpenWebUI
/var/lib/ai/openwebui/      /app/backend/data/
│                           │
├── webui.db                ├── webui.db           ← Base SQLite
├── uploads/                ├── uploads/           ← Fichiers uploadés
├── cache/                  ├── cache/             ← Cache
└── vector_db/              └── vector_db/         ← Base vectorielle
```

### 2.3 PostgreSQL — `/var/lib/ai/postgres` (VM) ↔ `/var/lib/postgresql/data` (conteneur)

```
okdsnoapps (VM)             Conteneur PostgreSQL
/var/lib/ai/postgres/       /var/lib/postgresql/data/
│                           │
├── pgdata/                 ├── pgdata/            ← Données PostgreSQL
│   ├── base/               │   ├── base/
│   ├── global/             │   ├── global/
│   ├── pg_wal/             │   ├── pg_wal/
│   └── ...                 │   └── ...
```

### 2.4 Redis — `/var/lib/ai/redis` (VM) ↔ `/data` (conteneur)

```
okdsnoapps (VM)             Conteneur Redis
/var/lib/ai/redis/          /data/
│                           │
├── appendonly.aof          ├── appendonly.aof     ← Persistance Redis
└── dump.rdb                └── dump.rdb           ← Snapshot Redis
```

---

## 3. Commandes de vérification

### Depuis le PC Fedora

```bash
# Lister les données Hermes
ls -la /var/data/hermes/
ls -la /var/data/hermes/profiles/

# Vérifier la taille
du -sh /var/data/hermes/
```

### Depuis le poste Windows (oc)

```bash
# Vérifier les répertoires sur la VM
oc debug node/okdsnoapps -- chroot /host ls -la /var/lib/ai/

# Vérifier l'intérieur des conteneurs
oc -n ai exec deployment/hermes -- ls -la /opt/data/profiles/
oc -n ai exec deployment/openwebui -- ls -la /app/backend/data/
```

---

## 4. Types de stockage

| Composant | Type | Machine hôte | Chemin hôte | Survit à |
|---|---|---|---|---|
| Hermes Agent | **NFS** | PC Fedora | `/var/data/hermes` | ✅ Redémarrage VM + OKD + pod |
| OpenWebUI | Local (Retain) | VM okdsnoapps | `/var/lib/ai/openwebui` | ✅ Redémarrage OKD + pod |
| PostgreSQL | Local (Retain) | VM okdsnoapps | `/var/lib/ai/postgres` | ✅ Redémarrage OKD + pod |
| Redis | Local (Retain) | VM okdsnoapps | `/var/lib/ai/redis` | ✅ Redémarrage OKD + pod |
