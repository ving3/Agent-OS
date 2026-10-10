# Anomalie 10 — Dashboard Agentic OS : panneaux et sidebar absents après restructuration

> **Date** : 2026-10-10
> **Contexte** : Restructuration du code agents-os (monolithe → 21 fichiers modulaires)
> **Impact** : Bloquant — Dashboard inutilisable (sidebar disparaît, profils non chargés)
> **Statut** : ✅ Résolu

---

## 1. Signalement

### Symptômes utilisateur

1. **Sidebar** : le menu latéral apparaît brièvement (environ 1 seconde) puis disparaît complètement
2. **Panneaux** : seul le panneau Dashboard (overview) est visible, tous les autres panneaux (Canvas, Graphe, Chat, Mémoire, Skills, Kanban, Administration) sont absents
3. **Bouton Administration** : le bouton d'administration n'apparaît pas dans la sidebar, même pour un utilisateur admin

### Constat technique initial

Les logs du pod agents-os montrent que seules les requêtes `/health` et `/api/status` sont reçues. Les endpoints `/api/profiles`, `/api/skills`, `/api/users` ne sont **jamais** appelés, ce qui indique que les fonctions JavaScript correspondantes (`loadProfiles()`, `loadSkills()`, `loadAdmin()`) ne s'exécutent pas.

---

## 2. Démarche de diagnostic

### Étape 1 — Vérification du HTML servi

**Action** : Récupérer le HTML du dashboard via `curl` et analyser sa structure.

**Résultat** :
```text
Page size: 47480 chars
panel-overview: 1 occurrence     panel-canvas: 1 occurrence
panel-graph: 1 occurrence        panel-chat: 1 occurrence
panel-memory: 1 occurrence       panel-skills: 1 occurrence
panel-kanban: 1 occurrence       panel-admin: 1 occurrence
Nav items: [overview, canvas, graph, chat, memory, skills, kanban, admin]
```

**Conclusion** : Le HTML est correct — tous les panneaux et tous les éléments de navigation sont présents dans le code source. Le problème n'est pas côté serveur.

### Étape 2 — Vérification du rendu Python (router.py)

**Action** : Examiner la méthode `_render_dashboard()` qui substitue les placeholders `{{USER_NAME}}`, `{{USER_ROLE}}`.

**Résultat** : La substitution fonctionne correctement — le HTML servi contient `var role='admin'` (au lieu de `{{USER_ROLE}}`).

**Conclusion** : Le problème n'est pas côté rendu serveur.

### Étape 3 — Vérification des endpoints API

**Action** : Tester chaque endpoint API directement via `curl` avec un token valide.

**Résultat** :
```json
GET /api/status → 200 OK
GET /api/profiles → 200 OK (7 profils)
GET /api/skills → 200 OK (58 compétences)
GET /api/users → 200 OK (admin)
```

**Conclusion** : Tous les endpoints fonctionnent parfaitement. Le problème est strictement **côté client** (navigateur).

### Étape 4 — Analyse du JavaScript servi

**Action** : Extraire le JavaScript du HTML servi et analyser la séquence d'initialisation.

**Résultat** :
```javascript
// Première ligne — initialisation des variables
var curAgent=null,agents={},skills=[],tasks=JSON.parse(localStorage.getItem('aos_tasks')||'[]'),chatHist={},canvasHist={};

// Seconde ligne — affichage du bouton admin
var role='admin';if(role==='admin')document.getElementById('admin-btn').style.display='flex';

// Troisième ligne — première fonction async
async function loadStatus(){...}
...
// Init — appel des fonctions de chargement
loadStatus();loadProfiles();loadSkills();renderKanban();loadAdmin();setInterval(loadStatus,10000);
```

**Observation critique** : La première ligne accède à `localStorage.getItem('aos_tasks')` **sans aucune protection**. Si `localStorage` est indisponible, une exception JavaScript est levée et **toute la suite du script est abandonnée**.

### Étape 5 — Vérification de l'hypothèse

**Analyse** : Dans un navigateur, plusieurs situations peuvent bloquer l'accès à `localStorage` :
- Navigation en mode privé / incognito (selon le navigateur)
- Restrictions de sécurité du navigateur (third-party cookies bloqués)
- Paramètres de confidentialité stricts
- Extension de navigateur bloquant le stockage local

Si `localStorage.getItem()` lève une exception, le JavaScript s'arrête immédiatement :
1. `role` n'est jamais défini → le bouton admin reste caché (`display:none`)
2. `loadProfiles()` n'est jamais appelée → aucun profil chargé → tous les panneaux vides
3. `loadAdmin()` n'est jamais appelée → pas de tableau des utilisateurs

---

## 3. Root Cause

**Cause racine** : Accès non protégé à `localStorage.getItem()` en JavaScript.

```javascript
// Code problématique (avant correction)
tasks=JSON.parse(localStorage.getItem('aos_tasks')||'[]')
```

Cette ligne est exécutée immédiatement au chargement du script, avant toute autre opération. Si `localStorage` lève une exception (`SecurityError`, `QuotaExceededError`, etc.), tout le script JavaScript s'arrête, ce qui empêche :

- L'affichage du bouton Administration (`admin-btn` reste en `display:none`)
- Le chargement des profils agents (`loadProfiles()` jamais appelée)
- Le chargement des compétences (`loadSkills()` jamais appelée)
- Le chargement de la liste des utilisateurs (`loadAdmin()` jamais appelée)
- Le rendu du Kanban (`renderKanban()` jamais appelée)

**Chaîne d'impact** :
```
localStorage.getItem() lève une exception
    ↓
Arrêt immédiat du script JavaScript
    ↓
var role='admin' jamais exécuté
    ↓
admin-btn reste display:none
    ↓
loadProfiles()/loadSkills()/loadAdmin() jamais appelées
    ↓
Tous les panneaux sauf overview sont vides
    ↓
Sidebar semble disparaître (pas de contenu dans les panneaux)
```

---

## 4. Solution appliquée

### Correction

```javascript
// AVANT (plantait si localStorage indisponible)
var tasks=JSON.parse(localStorage.getItem('aos_tasks')||'[]');

// APRÈS (résilient)
var tasks=[];
try { tasks=JSON.parse(localStorage.getItem('aos_tasks')||'[]'); }
catch(e) { tasks=[]; }
```

Même correction appliquée à la fonction `saveTasks()` :

```javascript
// AVANT
function saveTasks(){localStorage.setItem('aos_tasks',JSON.stringify(tasks));renderKanban();renderGraph();}

// APRÈS
function saveTasks(){try{localStorage.setItem('aos_tasks',JSON.stringify(tasks));}catch(e){}renderKanban();renderGraph();}
```

### Déploiement

```bash
# 1. Commit et push de la correction
git add agents-os/app/dashboard/templates.py
git commit -m "fix: securise l'acces localStorage dans le dashboard JS"
git push

# 2. Rebuild de l'image agents-os
oc start-build agents-os -n ai --from-dir=./agents-os --follow --wait

# 3. Déploiement automatique via ImageChange trigger
# Nouveau pod avec le JavaScript corrigé
```

---

## 5. Résultat

| Vérification | Avant | Après |
|-------------|-------|-------|
| Bouton Administration visible | ❌ Non | ✅ Oui |
| Profils agents chargés | ❌ Non | ✅ 7 profils |
| Compétences listées | ❌ Non | ✅ 58 compétences |
| Panneaux accessibles | ❌ 1/8 | ✅ 8/8 |
| Sidebar persistante | ❌ Disparaît | ✅ Reste visible |

---

## 6. Leçon apprise

### Règle générale

Tout accès au `localStorage` en JavaScript doit être protégé par un bloc `try/catch`.

```javascript
// À faire
try { value = localStorage.getItem('key'); } catch(e) { value = null; }

// À ne pas faire
value = localStorage.getItem('key');  // peut planter
```

### Contexte de la régression

La restructuration du code (passage d'un monolithe `main.py` de 1462 lignes à 21 fichiers modulaires) a déplacé le code JavaScript du template `DASHBOARD_HTML` de son contexte d'origine vers un fichier dédié (`dashboard/templates.py`). Le code JavaScript lui-même n'a pas été modifié — le bug était **préexistant** dans le code original, mais n'avait jamais été déclenché car les utilisateurs n'avaient pas de restrictions sur `localStorage`.

### Recommandation

Ajouter une vérification de disponibilité de `localStorage` au chargement de la page :

```javascript
function isLocalStorageAvailable() {
    try {
        localStorage.setItem('__test__', '1');
        localStorage.removeItem('__test__');
        return true;
    } catch(e) {
        return false;
    }
}
```

---

## Fichiers concernés

- `agents-os/app/dashboard/templates.py` (DASHBOARD_HTML → JavaScript)

## Voir aussi

- [Anomalie 9 — Agents OS hors service après restructuration](anomalie-09-agents-os-restructuration.md)
