# Anomalie 2 — Token JWT ArgoCD expiré

> **Date** : 2026-10-10
> **Contexte** : Synchronisation des applications ArgoCD via le CLI `argocd`
> **Impact** : Bloquant

---

## Contexte

Le CLI `argocd` utilise un token de session JWT d'une durée de validité d'environ 24 heures.
Après un certain temps d'inactivité, le token expire et toutes les commandes `argocd app sync`,
`argocd app list`, etc. échouent avec une erreur de permission.

---

## Symptôme

```text
rpc error: code = PermissionDenied desc = permission denied
```

---

## Choix possibles

| Solution | Description | Durée de vie |
|----------|-------------|-------------|
| **A** — Re-login | `argocd login` avec le mot de passe admin | 24h |
| **B** — Token API longue durée | Générer un token avec `argocd account generate-token` | Illimitée (révocable) |
| **C** — Refresh automatique | Script cron de refresh du contexte | 24h |

---

## Solution appliquée (A)

Re-login avec le mot de passe admin documenté dans `credentials/argocd-credentials.md` :

```bash
argocd login argocd-server-okd-gitops.apps.okdsnoapps.vmapps.home \
  --username admin --password <password> \
  --insecure --grpc-web --skip-test-tls \
  --name okdsnoapps-vmapps-home
```

Flags importants pour l'instance OKD :
- `--grpc-web` : obligatoire (HTTP/2 coupé par le routeur OKD)
- `--skip-test-tls` : obligatoire (certificats auto-signés derrière le routeur)
- `--insecure` : désactive la vérification TLS

---

## Résultat

Session JWT renouvelée pour 24h. Les commandes `argocd app sync` fonctionnent à nouveau.

---

## Recommandation

Pour les usages CI/CD ou l'automatisation, générer un token API longue durée :

```bash
argocd account generate-token --account admin
```

Puis l'utiliser via la variable d'environnement :

```bash
export ARGOCD_AUTH_TOKEN="<token>"
```

---

## Fichiers concernés

- `credentials/argocd-credentials.md` (mot de passe admin)
