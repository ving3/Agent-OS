# Anomalie 3 — Tag Hermes agent inexistant

> **Date** : 2026-10-10
> **Contexte** : Action M-04 (pinnage des images à des versions stables)
> **Impact** : Bloquant — ImagePullBackOff

---

## Contexte

Dans le cadre de l'action **M-04**, les images des déploiements doivent être pinnées à des
versions stables plutôt que d'utiliser le tag `latest`. Pour Hermes, le tag `0.3.14` a été
spécifié dans le manifest ArgoCD sans vérifier son existence sur Docker Hub.

---

## Symptôme

Le pod Hermes ne démarre pas :

```text
STATUS: ImagePullBackOff
```

---

## Analyse

Requête à l'API Docker Hub pour lister les tags disponibles :

```bash
curl -s "https://hub.docker.com/v2/repositories/nousresearch/hermes-agent/tags?page_size=30"
```

Résultat : aucun tag `0.3.14` ou `latest` n'existe. Les tags disponibles sont au format
`rc.X-v0.Y.Z-ARCH` :

| Tag | Description |
|-----|-------------|
| `rc.9-v0.21.7-amd64` | Dernier RC pour architecture amd64 |
| `rc.9-v0.21.7` | Multi-arch |
| `rc.8-v0.21.7-amd64` | RC précédent |
| `rc.7-v0.21.7-amd64` | RC plus ancien |

---

## Choix possibles

| Solution | Description | Fiabilité |
|----------|-------------|-----------|
| **A** — `rc.9-v0.21.7-amd64` | Tag valide, version stable, architecture explicite | Haute |
| **B** — `rc.9-v0.21.7` | Multi-arch, peut poser problème sur某些 nœuds | Moyenne |
| **C** — Revenir à `latest` | Tag inexistant — ne résout rien | Aucune |

---

## Solution appliquée (A)

```yaml
# argocd/manifests/hermes/deployment.yaml
image: nousresearch/hermes-agent:rc.9-v0.21.7-amd64
```

---

## Résultat

Pod Hermes redémarre avec l'image correcte :

```text
STATUS: 1/1 Running
```

---

## Leçon

Toujours vérifier les tags disponibles avant de spécifier une version :

```bash
# Vérifier les tags d'une image Docker
curl -s "https://hub.docker.com/v2/repositories/<org>/<image>/tags?page_size=30"
```

---

## Fichiers concernés

- `argocd/manifests/hermes/deployment.yaml`
