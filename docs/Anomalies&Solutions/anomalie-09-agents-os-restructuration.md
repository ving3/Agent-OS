# Anomalie 9 — Agents OS hors service après restructuration

> **Date** : 2026-10-10
> **Contexte** : Restructuration du code agents-os (monolithe → modules)
> **Impact** : Fonctionnel après rebuild

---

## Contexte

Le code d'`agents-os` a été restructuré : le fichier monolithique `main.py` (1462 lignes)
a été découpé en 21 fichiers modulaires organisés en 3 dossiers :

```
app/
├── main.py                  ← Point d'entrée
├── config.py                ← Configuration
├── database.py              ← Base SQLite
├── hermes_client.py         ← Client API Hermes
├── common/
│   ├── http_base.py         ← Classe HTTP de base
│   └── templates.py         ← Pages login/signup
├── dashboard/
│   ├── router.py            ← Routeur AgenticOSHandler
│   └── templates.py         ← Dashboard HTML + Admin HTML
└── panels/                  ← 8 dossiers de panneaux
    ├── overview/handler.py
    ├── skills/handler.py
    ├── chat/handler.py
    ├── admin/handler.py
    └── canvas/, graph/, memory/, kanban/ (client only)
```

---

## Symptôme

Le pod en cours d'exécution utilise l'ancienne image monolithique. Les nouveaux imports
ne sont pas disponibles :

```python
from panels.overview import handler as overview
# -> ModuleNotFoundError: No module named 'panels'
```

---

## Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — Rebuild de l'image | `oc start-build` avec le nouveau code |
| **B** — Modification à chaud | `oc cp` du nouveau code dans le pod en cours |
| **C** — Rollback | Revenir à l'ancien code monolithique |

---

## Solution appliquée (A)

```bash
# 1. Build de la nouvelle image
oc start-build agents-os -n ai --from-dir=./agents-os --follow --wait

# 2. Le déploiement se met à jour automatiquement
#    (annotation image.openshift.io/triggers)
```

---

## Résultat

Le nouveau pod charge correctement les modules :

```python
from panels.overview import handler as overview  # OK
from panels.skills import handler as skills      # OK
from panels.chat import handler as chat          # OK
from panels.admin import handler as admin_panel  # OK
```

Tests des endpoints après rebuild :

| Endpoint | Résultat |
|----------|----------|
| `GET /health` | ✅ `{"status": "ok"}` |
| `POST /api/login` | ✅ Token JWT reçu |
| `GET /dashboard` | ✅ HTTP 200 |
| `GET /api/status` | ✅ JSON complet |
| `GET /v1/models` | ✅ 5 modèles listés |
| `GET /api/skills` | ✅ Compétences listées |

---

## Fichiers concernés

- `agents-os/app/` (tous les fichiers de la nouvelle structure)
- `argocd/manifests/agents-os/buildconfig.yaml`

## Voir aussi

- [Anomalie 6 — NetworkPolicies builds](anomalie-06-networkpolicies-builds.md)
- [Anomalie 7 — contextDir résiduel](anomalie-07-contextdir-residuel.md)
