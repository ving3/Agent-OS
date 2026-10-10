# Anomalie 8 — Quoting PowerShell / WSL pour les commandes oc

> **Date** : 2026-10-10
> **Contexte** : Poste de travail Windows avec WSL Fedora-43
> **Impact** : Gênant — Commandes échouées, perte de temps

---

## Contexte

Le poste de travail est sous Windows 11. L'accès au cluster OpenShift se fait via
WSL Fedora-43 où `oc`, `argocd`, `helm` et `podman` sont installés. Les commandes
sont exécutées depuis PowerShell en utilisant `wsl -- <commande>`.

PowerShell interprète certains caractères avant de les passer à WSL, ce qui provoque
des échecs de commandes difficiles à diagnostiquer.

---

## Symptômes

```powershell
# Échec : les crochets [] sont interprétés comme un tableau PowerShell
wsl -- oc patch bc agents-os -n ai --type=json -p '[{"op":"remove","path":"..."}]'
# -> Erreur: there is no need to specify a resource type as a separate argument

# Échec : les guillemets et $ sont interprétés
wsl -- bash -c "oc get pods -o jsonpath='{.items[0].metadata.name}'"
# -> Le $ est interprété par PowerShell comme une variable
```

---

## Caractères problématiques

| Caractère | Interprété par PowerShell | Problème |
|-----------|--------------------------|----------|
| `$` | Début de variable | `$var` → valeur de la variable |
| `'` | Chaîne littérale | Conflit avec les guillemets bash |
| `"` | Chaîne interprétée | Conflit avec les guillemets bash |
| `{ }` | Début/fin de bloc | Commande non reconnue |
| `[ ]` | Accès tableau | Erreur d'arguments |
| `( )` | Subexpression | Erreur de parsing |

---

## Solutions appliquées

### Approche A — Scripts fichiers (recommandée)

```powershell
# 1. Créer un fichier .sh dans le projet
# 2. Copier dans WSL et exécuter
wsl -- bash /home/ving/script.sh
```

Le script WSL peut être copié depuis Windows :

```powershell
wsl -- cp /mnt/c/Users/ving/Projets/Agent-OS/script.sh /home/ving/script.sh
wsl -- bash /home/ving/script.sh
```

### Approche B — Commandes simples

```powershell
# OK — pas de caractères spéciaux PowerShell
wsl -- argocd app list
wsl -- oc get pods -n ai
wsl -- podman --version
```

---

## Règle empirique

> Si la commande contient `$`, `'`, `"`, `{`, `}`, `[`, `]`, `(`, `)` — utiliser
> un script fichier. Sinon, l'inline fonctionne.

---

## Résultat

L'utilisation systématique de scripts fichiers pour les commandes complexes a éliminé
les erreurs de quoting. Les commandes simples restent en inline.
