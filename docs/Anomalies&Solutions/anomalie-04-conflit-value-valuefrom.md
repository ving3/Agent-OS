# Anomalie 4 — Conflit value / valueFrom sur le déploiement Hermes

> **Date** : 2026-10-10
> **Contexte** : Migration du déploiement manuel vers ArgoCD
> **Impact** : Bloquant — Sync ArgoCD échouée

---

## Contexte

Le déploiement Hermes existant (déployé manuellement avant ArgoCD) avait la variable
d'environnement `OPENAI_API_KEY` définie avec une `value` en clair (la clé API BytePlus
directement dans le YAML de déploiement).

Le nouveau manifest ArgoCD utilise `valueFrom` avec un `secretKeyRef` pour référencer
le secret `ai-secrets`. Lors de la synchronisation, ArgoCD tente de patcher le déploiement
existant, mais Kubernetes refuse car un champ `env[].valueFrom` ne peut pas coexister
avec `env[].value`.

---

## Symptôme

```text
error when patching Deployment.apps "hermes" is invalid:
  spec.template.spec.containers[0].env[10].valueFrom:
  Invalid value: "": may not be specified when `value` is not empty
```

---

## Choix possibles

| Solution | Description | Risque |
|----------|-------------|--------|
| **A** — Supprimer le déploiement | `oc delete deploy hermes` puis resync ArgoCD | Interruption temporaire |
| **B** — Modifier le déploiement existant | `oc edit deploy hermes` pour aligner sur le manifest | Manuel, erreur possible |
| **C** — Ignorer la différence | Configurer ArgoCD pour ignorer ce champ via `ignoreDifferences` | Le secret ne serait pas utilisé |

---

## Solution appliquée (A)

```bash
# Supprimer le déploiement existant (les données sont sur le PVC)
oc delete deploy hermes -n ai

# ArgoCD recrée automatiquement le déploiement avec les bonnes spécifications
# La resync est automatique (syncPolicy: automated)
```

---

## Résultat

ArgoCD recrée le déploiement Hermes avec `valueFrom: secretKeyRef` et le pod démarre
correctement. La variable `OPENAI_API_KEY` est maintenant lue depuis le secret `ai-secrets`.

---

## Fichiers concernés

- `argocd/manifests/hermes/deployment.yaml`
- `argocd/manifests/ai-infra/secret-template.yaml`

## Note

Les données d'Hermes sont stockées sur le PVC `hermes-data` (10Gi) qui n'est pas affecté
par la suppression du déploiement. Les profiles, skills et mémoires des agents sont conservés.
