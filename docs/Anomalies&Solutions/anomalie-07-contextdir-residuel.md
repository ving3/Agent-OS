# Anomalie 7 — contextDir résiduel du build Git

> **Date** : 2026-10-10
> **Contexte** : Build Binary après changement du type de build (Binary → Git → Binary)
> **Impact** : Bloquant — Build échoué

---

## Contexte

Le BuildConfig d'`agents-os` a été modifié de `type: Binary` à `type: Git` puis
repassé en `type: Binary`. Le champ `spec.source.contextDir: agents-os`, qui était
nécessaire pour le build Git (le Dockerfile est dans `agents-os/`), a été conservé
dans la configuration.

Lors d'un build Binary, `contextDir` est interprété comme un sous-chemin du répertoire
uploadé. Comme la commande `oc start-build --from-dir=./agents-os` upload déjà le
dossier `agents-os/`, le contexte devient `agents-os/agents-os/` — qui n'existe pas.

---

## Symptôme

```text
Receiving source from STDIN as archive ...
error: provided context directory does not exist: agents-os
```

---

## Choix possibles

| Solution | Description |
|----------|-------------|
| **A** — Supprimer `contextDir` | Retirer le champ du BuildConfig |
| **B** — Uploader depuis le parent | `--from-dir=.` au lieu de `--from-dir=./agents-os` |
| **C** — Ignorer (repartir d'un Git clean) | Re-créer le BuildConfig depuis zéro |

---

## Solution appliquée (A)

```bash
oc patch bc agents-os -n ai --type=json \
  -p '[{"op":"remove","path":"/spec/source/contextDir"}]'
```

---

## Résultat

Le build Binary fonctionne correctement sans `contextDir` :

```bash
oc start-build agents-os -n ai --from-dir=./agents-os --follow --wait
# Build agents-os-17: Complete
```

---

## Fichiers concernés

- `argocd/manifests/agents-os/buildconfig.yaml`
- `agents-os/okd-build.yaml` (DEPRECATED)

## Voir aussi

- [Anomalie 5 — BuildConfig Binary → Git](anomalie-05-buildconfig-binary-git.md)
- [Anomalie 6 — NetworkPolicies builds](anomalie-06-networkpolicies-builds.md)
