# Problèmes connus

Chaque problème confirmé doit recevoir un identifiant stable et rester ici jusqu'à sa correction, laquelle doit être référencée dans `CHANGELOG.md`.

## Ouverts

### ISSUE-022 — Création réelle du grugeage IPE à valider dans Fusion

- **État :** fonctionnement de base V1.18.0 validé dans Fusion ; essais étendus restant à effectuer.
- **Périmètre :** principale IPE, HEA ou HEB, secondaire IPE droite et axes à `90°`.
- **Impact :** la prévisualisation et la création à `90°` sont validées avec une principale longue, une principale trop courte et deux grugeages aux extrémités opposées de la même secondaire. Les variantes de taille, d'ancrage, de rotation et de miroir restent à contrôler avant extension à d'autres angles ou familles.
- **Sécurité :** la création exige un corps secondaire unique et un volume réellement retiré ; toute tentative incomplète supprime ses attributs, coupes, esquisses, plans et prolongements.
- **Validation prévue :** terminer le test 22 sur plusieurs tailles, orientations, miroirs et points d'ancrage.

### ISSUE-021 — Barre principale trop courte non prolongée

- **Symptôme :** lors d'une jonction ajustée près de l'extrémité de la principale, la secondaire est coupée mais une partie de sa section reste sans appui parce que la principale s'arrête sur l'axe commun.
- **Cause :** la V1.16.2 contrôlait uniquement le franchissement du plan par la barre secondaire ; elle supposait que la principale couvrait déjà toute la section de contact.
- **Correction V1.16.3 :** la section réelle de la secondaire est projetée sur le plan de contact, sa portée sur l'axe principal est comparée au corps principal actuel, puis chaque extrémité insuffisante est prolongée et contrôlée avant la coupe.
- **Validation prévue :** reprendre le cas des captures du 20 août, vérifier la présence de `PROLONGEMENT_BARRE_PRINCIPALE` et l'absence de vide sous toute la section secondaire.

### ISSUE-020 — Onglet encore incomplet selon l'orientation interne de la face

- **Symptôme :** avec des IPE ancrés à l'axe, les semelles suivent le plan diagonal mais une partie de l'âme reste manquante.
- **Cause V1.16.1 :** toute la face était bien prise en compte pour calculer la longueur, mais l'extrusion utilisait toujours `PositiveExtentDirection`. Selon l'orientation interne de la face B-Rep, ce sens peut pointer vers l'intérieur de la barre.
- **Correction V1.16.2 :** les deux directions sont essayées de manière réversible et la face finale doit être entièrement au-delà du plan ; sinon la création est annulée avec le détail des deux tentatives.
- **Validation prévue :** recréer un seul coin IPE du document signalé, puis contrôler l'âme et les deux semelles avant de traiter les autres coins.

### ISSUE-019 — Géométries courbes avancées encore limitées

- **État :** périmètre restant après la V1.16.0.
- **Impact :** la jonction ajustée accepte une barre de référence droite et une barre à ajuster droite ou cintrée, à tout angle non parallèle. L'onglet symétrique reste limité à deux chemins droits. Une référence cintrée, un onglet entre arcs, les grugeages hors du cas IPE droit à `90°`, les platines et les boulons ne sont pas encore pris en charge ; la V1.18.0 ajoute la première création réelle du double grugeage IPE à valider.
- **Sécurité :** la position et l'orientation du plan final sont contrôlées contre la prévisualisation avant toute coupe ; les cas hors périmètre sont refusés sans modifier le modèle.
- **Validation prévue :** terminer les essais du test 21 avant d'étendre le même modèle géométrique aux références cintrées.

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

### ISSUE-008 — Matériaux européens limités au document actif

- **État :** limitation de l'API Fusion acceptée pour la V1.9.0.
- **Cause :** l'API publique `Materials.addByCopy` copie un matériau vers un document, mais pas vers une bibliothèque globale ou les Favoris.
- **Impact :** les nuances S235JR, S275JR et S355J2 sont vérifiées ou créées séparément dans chaque document utilisé avec le complément.
- **Prévention :** nouvelle vérification à chaque démarrage avec un document actif et à chaque ouverture de la commande de création.

### ISSUE-014 — Import personnalisé limité au DXF ASCII R12 en millimètres

- **État :** limitation acceptée pour la V1.11.0.
- **Impact :** un fichier binaire, une version DXF plus récente, une autre unité ou une entité non prise en charge est refusé au lieu d'être converti silencieusement.
- **Suite :** élargir les formats seulement après des essais garantissant les dimensions, les courbes et les contours fermés.

### ISSUE-015 — Restauration sans interface Fusion

- **État :** limitation acceptée pour la V1.11.0.
- **Impact :** une suppression conserve bien le DXF et ses métadonnées dans la corbeille locale, mais aucune commande de restauration n'est encore disponible dans l'extension.
- **Suite :** ajouter une restauration contrôlée après validation de l'ajout et de la suppression.

## Résolus pendant la préparation de la V1

### ISSUE-018 — Aperçu absent sur un chemin déjà occupé

- **Symptôme :** avec une barre existante signalée dans `Utilisation des chemins`, la sélection reste bleue mais aucun profil jaune n'apparaît tant que le remplacement n'est pas activé.
- **Cause :** le blocage volontaire du bouton `OK` rendait la commande invalide pour Fusion, qui pouvait alors ne pas rappeler son événement standard d'aperçu.
- **Correction V1.11.3 :** l'événement de changement des entrées rafraîchit aussi directement l'aperçu ; le contrôle de sécurité du bouton `OK` reste indépendant.
- **Validation attendue :** sélectionner un chemin occupé, vérifier immédiatement le profil jaune avec `OK` désactivé, puis cocher le remplacement et créer.

### ISSUE-017 — Ancrage opposé entre l'aperçu et la barre finale selon le document

- **Symptôme :** dans le document `implantation`, un coin placé en bas à gauche dans l'aperçu jaune se retrouve en haut à droite après la création, alors que d'autres dessins ne présentent aucun saut.
- **Cause :** l'aperçu définissait son repère transversal depuis le squelette, tandis que les axes du plan perpendiculaire étaient choisis automatiquement par Fusion. Selon le repère et le sens de l'esquisse du document, les deux axes pouvaient être opposés.
- **Correction V1.11.2 :** lecture des axes réels de l'esquisse importée, calcul du changement de base vers le repère commun du chemin, puis composition avec la rotation et les miroirs demandés. Un repère déjà correct reste inchangé.
- **Validation attendue :** le même point d'ancrage doit rester sur la ligne dans `implantation` et dans un second document qui fonctionnait déjà avant la correction.

### ISSUE-016 — Chemin déjà occupé non signalé

- **Symptôme :** la commande autorisait plusieurs barres créées par l'extension sur une même ligne ou un même arc sans avertissement.
- **Cause :** les jetons de liaison au squelette étaient enregistrés mais pas consultés avant une nouvelle création.
- **Correction V1.11.1 :** détection des liaisons existantes, blocage des doublons par défaut et remplacement explicite avec création de la nouvelle barre avant retrait de l'ancienne.
- **Validation attendue :** sélectionner un chemin déjà utilisé, vérifier le blocage puis remplacer volontairement la barre sans toucher aux autres chemins.

### ISSUE-013 — Copies masquées derrière le matériau générique « Acier »

- **Symptôme :** le menu de la V1.9.5 affiche seulement `Acier — Document actif` au lieu des nuances S235JR, S275JR et S355J2 attendues.
- **Diagnostic réel :** le journal de la V1.9.6 confirme `3 existant(s), 0 créé(s)` ; les trois nuances portent donc les bons noms, mais leurs copies partagent le même identifiant interne Autodesk que `Acier`.
- **Tentative V1.9.6 :** le renommage explicite n'a pas corrigé l'affichage puisque les noms étaient déjà enregistrés correctement.
- **Cause :** l'inventaire dédupliquait à tort tous les matériaux du document uniquement avec cet identifiant partagé, puis la résolution par identifiant pouvait également retrouver `Acier`.
- **Correction :** la V1.9.7 distingue les entrées du document par leur position et leur nom exact, tout en conservant l'identifiant réel pour la traçabilité.
- **Sécurité :** si l'ordre change avant la création, la résolution retombe sur un nom unique et refuse explicitement toute ambiguïté.
- **Validation attendue :** les trois nuances apparaissent en tête du menu sous la source `Document actif`.

### ISSUE-012 — Nuances EI_JHR invisibles dans la longue liste Fusion

- **Symptôme :** après un démarrage réussi, le menu semblait ne contenir que les matériaux Autodesk.
- **Cause :** le tri alphabétique plaçait les nuances S235/S355 après les nombreuses entrées `Acier`, et le matériau générique restait sélectionné.
- **Correction :** la V1.9.4 place les matériaux du document en tête et sélectionne le S235JR par défaut.
- **Validation attendue :** les trois premières lignes visibles sont S235JR, S275JR et S355J2 avec la source `Document actif`.

### ISSUE-011 — Coefficient de Poisson traité comme une grandeur avec unité

- **Symptôme :** la V1.9.2 refusait `0.3` car Fusion associait une chaîne d'unité interne non vide au coefficient de Poisson.
- **Cause :** la détection reposait à tort sur une chaîne d'unité vide pour reconnaître une valeur sans dimension.
- **Correction :** la V1.9.3 traite toujours `poisson_ratio` comme un nombre pur et ignore l'identifiant d'unité associé.
- **Validation attendue :** création complète des deux matériaux puis démarrage du complément.

### ISSUE-010 — Nom interne d'unité non reconnu dans la V1.9.1

- **Symptôme :** la densité expose `KilogramPerCubicMeter` au lieu du symbole `kg/m³` attendu par la première correction.
- **Cause :** selon la propriété et la version de Fusion, `FloatProperty.units` peut renvoyer un identifiant Autodesk interne.
- **Correction :** la V1.9.2 reconnaît les identifiants internes Autodesk et leurs équivalents symboliques pour la densité et les pressions.
- **Validation attendue :** démarrage sans erreur, puis présence unique des trois nuances dans le document actif.

### ISSUE-009 — Conversion de densité refusée au démarrage de la V1.9.0

- **Symptôme :** `FusionUnitsManager.convert` renvoyait `The units parameter is not a valid unit string` pendant la création du S235JR.
- **Cause :** le convertisseur général de la conception Fusion n'accepte pas la chaîne d'unité exposée par la propriété physique de densité dans ce contexte.
- **Correction :** la V1.9.1 convertit directement les valeurs SI vers l'unité déclarée par chaque propriété de matériau, sans dépendre du convertisseur Fusion défaillant.
- **Prévention :** tests couvrant plusieurs écritures usuelles de densité et de pression avant toute installation.

### ISSUE-007 — Planification DXF refusée depuis le bouton

- **Cause :** le premier essai appelait `fireCustomEvent` directement depuis l'événement `Execute` de la commande.
- **Correction :** déclenchement depuis un thread de travail après la fermeture du bouton, avec trois tentatives courtes et bornées.
- **Validation :** création depuis le DXF confirmée dans Fusion par l'utilisateur.

### ISSUE-006 — Contour IPE déformé dans l'esquisse Fusion

- **Cause :** la reconstruction manuelle enchaînait les segments depuis l'extrémité inversée de certains arcs Fusion.
- **Correction :** reconstruction manuelle supprimée ; import direct de `profiles/IPE/IPE_100.dxf` avec contrôle des dimensions et de l'ancrage.
- **Validation :** profil et extrusion confirmés dans Fusion par l'utilisateur.

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
