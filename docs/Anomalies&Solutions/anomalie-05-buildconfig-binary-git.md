# Anomalie 5 — BuildConfig Binary → Git incompatible

> **Date** : 2026-10-10
> **Contexte** : Action A-02 (conversion du build Binary en build Git)
> **Impact** : Mineur — OutOfSync assumé

---

## Contexte

Dans le cadre de l'action **A-02**, le BuildConfig d'`agents-os` a été modifié de
`type: Binary` à `type: Git` pour s'intégrer dans le workflow GitOps ArgoCD.
Le BuildConfig Git pointe vers `https://github.com/ving3/Agent-OS.git` avec un
`contextDir: agents-os`.

Problème : le dépôt GitHub est **privé** et aucun secret d'authentification (`sourceSecret`)
n'a été configuré sur le BuildConfig. Sans token GitHub, le build ne peut pas cloner
le dépôt.

---

## Symptôme

ArgoCD signale un `OutOfSync` permanent sur l'application `agents-os` :

```text
STATUS: OutOfSync
```

Le BuildConfig du cluster (type: Binary, build manuel) ne correspond pas au manifest
(type: Git).

---

## Choix possibles

| Solution | Description | Complexité | Effort |
|----------|-------------|------------|--------|
| **A** — Revenir à Binary | Build manuel via `oc start-build`, OutOfSync assumé | Faible | 1 commande |
| **B** — Git avec secret | Ajouter `sourceSecret` au BuildConfig + token GitHub | Moyenne | Création secret + patch |
| **C** — CI externe | Build via GitHub Actions, push vers le registry OKD | Élevée | Configuration CI complète |

---

## Solution appliquée (A)

Le BuildConfig est maintenu en **Binary** pour les builds manuels. ArgoCD reste en
`OutOfSync` sur ce point, mais le déploiement fonctionne avec la dernière image buildée.

```bash
# Build manuel après modification du code
oc start-build agents-os -n ai --from-dir=./agents-os --follow --wait
```

---

## Résultat

- L'application `agents-os` reste `OutOfSync` dans ArgoCD (uniquement le BuildConfig)
- Le déploiement et l'application sont **fonctionnels**
- Les builds manuels restent possibles

---

## Évolution possible

Pour résoudre définitivement, opter pour la solution **C** (GitHub Actions) :

```yaml
# .github/workflows/build-agents-os.yml
name: Build agents-os
on:
  push:
    branches: [main]
    paths: ['agents-os/**']
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Build and push to OKD registry
        run: |
          podman build -t agents-os:latest ./agents-os
          podman push agents-os:latest <registry>/ai/agents-os:latest
```

---

## Fichiers concernés

- `argocd/manifests/agents-os/buildconfig.yaml`
- `agents-os/okd-build.yaml` (DEPRECATED)
