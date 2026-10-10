# Anomalie 6 — NetworkPolicies bloquant les builds OpenShift

> **Date** : 2026-10-10
> **Contexte** : Action M-02 (isolation réseau du namespace `ai`)
> **Impact** : Bloquant — GenericBuildFailed

---

## Contexte

L'action **M-02** a ajouté 5 NetworkPolicies dans le namespace `ai` pour isoler le
trafic réseau :

1. `allow-dns` — résolution DNS
2. `allow-router-ingress` — accès routeur OKD
3. `allow-intra-namespace` — trafic interne
4. `allow-egress-llm` — egress Hermes → BytePlus API
5. `allow-egress-registry` — egress agents-os → registry interne

Ces politiques restreignent l'egress : seuls les pods correspondant aux sélecteurs
peuvent sortir du namespace. Les pods de build OpenShift (créés par `oc start-build`)
ne correspondent à **aucun sélecteur** existant et sont donc bloqués.

---

## Symptôme

**Phase 1** — Pull de l'image de base impossible :

```text
Pulling image python:3.11-slim ...
Trying to pull registry.redhat.io/python:3.11-slim...
  -> dial tcp 98.88.164.131:443: i/o timeout
  -> dial tcp 32.199.33.133:443: i/o timeout
error: GenericBuildFailed
```

**Phase 2** — Après correction partielle, push vers le registry interne impossible :

```text
Pushing image image-registry.openshift-image-registry.svc:5000/ai/agents-os:latest ...
  -> dial tcp 172.30.184.102:5000: i/o timeout
```

---

## Analyse

Les pods de build OpenShift ont des labels spécifiques comme `openshift.io/build.name=agents-os-16`.
Ces labels ne sont pas pris en compte par les NetworkPolicies existantes qui utilisent
`app.kubernetes.io/name` comme sélecteur.

---

## Choix possibles

| Solution | Description | Sécurité |
|----------|-------------|----------|
| **A** — NP dédiées aux builds | Créer des policies ciblant `openshift.io/build.name` | Haute (ciblée) |
| **B** — Egress large | Policy `allow-all-egress` pour tout le namespace | Faible (trop permissive) |
| **C** — Build dans un autre namespace | Déplacer les builds hors du namespace `ai` | Moyenne (complexe) |

---

## Solution appliquée (A)

Deux NetworkPolicies ajoutées :

```yaml
# 1. Pull images depuis Docker Hub / PyPI
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-egress-builds
  namespace: ai
spec:
  podSelector:
    matchExpressions:
      - key: openshift.io/build.name
        operator: Exists
  policyTypes:
    - Egress
  egress:
    - ports:
        - port: 443
          protocol: TCP
        - port: 80
          protocol: TCP
---
# 2. Push vers le registry interne OKD
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-egress-builds-registry
  namespace: ai
spec:
  podSelector:
    matchExpressions:
      - key: openshift.io/build.name
        operator: Exists
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: openshift-image-registry
      ports:
        - port: 5000
          protocol: TCP
```

---

## Résultat

Les builds peuvent désormais :
1. **Puller** les images de base depuis Docker Hub (`python:3.11-slim`)
2. **Pusher** l'image finale vers le registry interne OKD

Le build agents-os #17 a été complété avec succès après l'application de ces policies.

---

## Fichiers concernés

- `argocd/manifests/ai-infra/networkpolicy.yaml`

## Voir aussi

- [Anomalie 7 — contextDir résiduel](anomalie-07-contextdir-residuel.md)
