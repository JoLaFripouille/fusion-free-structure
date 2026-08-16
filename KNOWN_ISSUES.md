# Problèmes connus

Chaque problème confirmé doit recevoir un identifiant stable et rester ici jusqu'à sa correction, laquelle doit être référencée dans `CHANGELOG.md`.

## Ouverts

### ISSUE-001 — Validation réelle dans Fusion à terminer

- **État :** ouvert
- **Impact :** la syntaxe, l'API locale et la géométrie sont vérifiées, mais la mise à jour du corps après modification d'une ligne doit encore être prouvée dans l'application.
- **Test prévu :** `docs/TEST_PROTOCOL_FUSION.md`.

### ISSUE-002 — Profil V1 fixe

- **État :** limitation acceptée
- **Impact :** la commande crée seulement un IPE 100, même si les 341 DXF sont inclus.
- **Suite :** sélection par famille et dimension prévue dans `ROADMAP.md`.

### ISSUE-003 — Portée limitée au composant racine

- **État :** limitation acceptée
- **Impact :** les lignes appartenant à une esquisse placée dans un sous-composant sont refusées explicitement.

### ISSUE-004 — Licence non choisie

- **État :** décision utilisateur requise
- **Impact :** le dépôt est visible publiquement, mais il ne donne pas encore de permission générale de réutilisation.

### ISSUE-005 — Essai Fusion en attente d'un lancement manuel

- **État :** ouvert, environnement de test uniquement
- **Symptôme :** le pilotage automatique de la fenêtre Fusion échoue avant toute interaction avec `GetCursorPos failed: Accès refusé (0x80070005)`.
- **Impact :** aucun ; le complément est installé, mais son essai réel n'a pas encore démarré et aucune conclusion fonctionnelle ne doit être tirée de cette erreur externe.
- **Suite :** lancer manuellement le complément depuis **Scripts et compléments**, puis reprendre le protocole `docs/TEST_PROTOCOL_FUSION.md`.

## Résolus pendant la préparation de la V1

### ISSUE-0001 — Identifiant produit du manifeste

- **Cause :** valeur générique non conforme au modèle local Fusion.
- **Correction :** utilisation de `autodeskProduct: Fusion` après comparaison avec l'installation présente.
- **Prévention :** valider le manifeste contre l'API et les modèles installés avant tout chargement.

### ISSUE-0002 — Méthode initiale de préparation du dépôt refusée

- **Cause :** une seule opération combinait copie et nettoyage récursif, ce qui a déclenché la protection locale.
- **Correction :** création explicite des dossiers et copie sélective des seuls fichiers autorisés, sans suppression.
- **Prévention :** séparer préparation, vérification et nettoyage ; éviter tout nettoyage lorsqu'une liste blanche de copie suffit.

### ISSUE-0003 — Hypothèses incorrectes dans les premiers tests du dépôt

- **Cause :** le test géométrique pointait vers l'ancien emplacement du module et le test DXF exigeait `$INSUNITS`, champ absent du format R12.
- **Correction :** chemin d'import rendu relatif à la nouvelle arborescence et contrôle limité aux garanties réelles du R12 ; la convention millimétrique est explicitée dans le README.
- **Prévention :** distinguer les propriétés réellement encodées dans un format ancien des conventions validées au moment de l'export.

### ISSUE-0004 — Bytecode Python contenant des chemins locaux

- **Cause :** la compilation et les tests ont généré huit fichiers `.pyc` dont la métadonnée `co_filename` contenait le chemin absolu du dossier de travail.
- **Risque :** faible divulgation d'informations si le dossier brut était archivé, malgré l'exclusion déjà présente dans `.gitignore`.
- **Correction :** caches déplacés hors du dépôt dans une quarantaine temporaire récupérable ; publication limitée à l'index Git vérifié.
- **Prévention :** tests lancés avec `python -B` et contrôle automatique interdisant `.pyc` et `__pycache__` dans le payload.

### ISSUE-0005 — Suppression automatique des caches refusée deux fois

- **Cause :** la protection locale a refusé une suppression récursive, d'abord sur des chemins calculés puis sur quatre chemins absolus explicites.
- **Correction :** déplacement récupérable et borné des quatre dossiers vers une quarantaine temporaire, sans suppression.
- **Prévention :** préparer les livraisons dans un dossier propre et lancer les tests avec l'écriture du bytecode désactivée.
