# Protocole d'essai Fusion — V1

Effectuer l'essai dans un nouveau document sans donnée de production.

Lors d'un import manuel d'un DXF de la bibliothèque, sélectionner explicitement les millimètres : le format R12 ne contient pas de champ `$INSUNITS`.

## Test 1 — Une barre

1. Créer un nouveau modèle avec l'historique de conception activé.
2. Dans le composant racine, créer une esquisse sur le plan XY.
3. Tracer une ligne horizontale contrainte à `200 mm`, puis terminer l'esquisse.
4. Lancer **Profil acier V1**, conserver la famille `IPE` et la section `100`, puis sélectionner la ligne.
5. Avant de valider, vérifier qu'un aperçu jaune semi-transparent suit la ligne sans ajouter de composant dans l'arborescence.
6. Retirer puis resélectionner la ligne et vérifier que l'aperçu disparaît puis réapparaît.
7. Valider la commande.
8. Attendre le message confirmant que la barre a été créée depuis le DXF ; l'import est volontairement exécuté juste après la fermeture de la commande.
9. Vérifier la présence d'un composant `BARRE_IPE100_001` contenant un plan, une esquisse DXF, un balayage et un corps.
10. Ouvrir l'esquisse de section et vérifier que son contour correspond exactement au DXF source, avec quatre raccords corrects.
11. Mesurer la section : largeur `55 mm`, hauteur `100 mm`.
12. Mesurer la barre : longueur `200 mm`.

## Test 2 — Mise à jour paramétrique

1. Modifier la longueur de la ligne du squelette de `200 mm` à `300 mm`.
2. Terminer l'esquisse et laisser Fusion recalculer.
3. Vérifier que la barre mesure `300 mm` et que sa section reste `55 × 100 mm`.
4. Vérifier qu'aucun nouveau composant ou corps parasite n'est apparu.

## Test 3 — Sélection multiple

1. Ajouter une deuxième ligne droite non colinéaire au squelette.
2. Relancer la commande et sélectionner deux lignes encore non traitées.
3. Vérifier qu'un composant indépendant est créé pour chacune.

## Test 4 — Profil cintré sur un arc

1. Ajouter dans le composant racine un arc de `90°` et de rayon `500 mm`.
2. Relancer la commande et sélectionner uniquement cet arc.
3. Vérifier que l'aperçu jaune suit l'arc avant de valider.
4. Vérifier qu'un composant indépendant est créé.
5. Vérifier que l'IPE suit l'arc entier, avec sa section perpendiculaire au chemin.
6. Ouvrir l'esquisse DXF et contrôler que la section reste `55 × 100 mm` avec ses quatre raccords corrects.
7. Modifier le rayon ou l'angle de l'arc, puis vérifier que la barre cintrée se recalcule sans créer un nouveau composant.

## Test 5 — Choix de la famille et de la section

Effectuer chaque essai sur une nouvelle ligne droite de `200 mm` afin d'isoler les erreurs.

1. Ouvrir la commande et choisir la famille `HEA`, puis la section `160`.
2. Vérifier que la liste des sections change lorsque la famille change.
3. Sélectionner la ligne et vérifier que l'aperçu jaune devient un HEA 160.
4. Valider, puis mesurer la section créée : `160 × 152 mm`.
5. Recommencer avec `Tube carré`, section `80 × 80 — ép. 4 mm`.
6. Vérifier dans l'aperçu la présence du contour extérieur et du contour intérieur.
7. Valider, puis vérifier une enveloppe extérieure `80 × 80 mm`, une épaisseur `4 mm` et un corps creux unique.
8. Recommencer avec `Tube rond`, section `Ø 60.3 — ép. 3 mm`.
9. Vérifier une enveloppe extérieure de diamètre `60.3 mm`, une épaisseur `3 mm` et un corps creux unique.

## Test 6 — Points d'ancrage

Tester d'abord l'affichage et l'aperçu, puis créer une seule barre à la fois.

1. Ouvrir la commande avec `IPE 100` et vérifier une grille de neuf points bleus avec le centre rouge.
2. Sélectionner une ligne droite et cliquer successivement sur les neuf points.
3. Vérifier qu'un seul point reste rouge et que les huit autres redeviennent bleus.
4. Vérifier que l'aperçu jaune se déplace à chaque clic et que le point actif reste sur la ligne.
5. Choisir `Haut gauche`, valider et vérifier que le composant contient `ESQUISSE_IPE100_DXF_ANCRAGE_TL` et l'attribut `anchor = TL`.
6. Recommencer avec une cornière inégale afin de vérifier le comportement sur un profil asymétrique.
7. Recommencer avec un tube rectangulaire afin de vérifier que le changement d'ancrage ne supprime pas le contour intérieur.

## Test 7 — Rotation autour de l'ancrage

Procéder en deux petites phases. Ne lancer la phase B qu'après validation complète de la phase A.

### Phase A — Aperçu uniquement

1. Arrêter puis exécuter le complément et vérifier que le bouton indique `Profil acier V1.5.0`.
2. Ouvrir la commande avec `IPE 100`, conserver l'ancrage central et sélectionner une ligne droite.
3. Vérifier que le nouveau champ `Rotation` vaut `0°` et que l'aperçu n'a pas changé de position.
4. Saisir successivement `45°`, `90°` puis `-30°` sans valider la commande.
5. Vérifier que l'aperçu jaune pivote immédiatement et reste centré sur le même point rouge.
6. Choisir `Haut gauche`, répéter `0°` puis `90°` et vérifier que ce coin reste sur le chemin pendant toute la rotation.
7. Annuler la commande sans créer de barre.

### Phase B — Géométrie finale

1. Après validation de la phase A, créer un IPE 100 à `45°` avec l'ancrage `Haut gauche`.
2. Vérifier que le corps final remplace l'aperçu sans saut de position ni d'orientation.
3. Ouvrir l'esquisse DXF et vérifier les quatre raccords, la fermeture du contour et l'attribut `rotation_deg = 45`.
4. Recommencer avec un tube rectangulaire à `90°` afin de vérifier la conservation du contour intérieur.

## Test 8 — Miroirs X et Y

Commencer par un profil asymétrique pour que chaque inversion soit visible sans ambiguïté.

### Phase A — Aperçu uniquement

1. Arrêter puis exécuter le complément et vérifier que le bouton indique `Profil acier V1.6.0`.
2. Choisir une `Cornière inégale`, l'ancrage `Haut gauche`, une rotation de `0°`, puis sélectionner une ligne.
3. Vérifier que deux boutons `Miroir X` et `Miroir Y` sont présents et désactivés par défaut.
4. Activer uniquement `Miroir X` et vérifier l'inversion horizontale immédiate de l'aperçu.
5. Désactiver X, activer uniquement `Miroir Y` et vérifier l'inversion verticale.
6. Activer X et Y simultanément et vérifier que les deux boutons restent actifs.
7. Saisir ensuite une rotation de `45°` et vérifier que le même coin d'ancrage reste sur le chemin.
8. Annuler la commande sans créer de barre.

### Phase B — Géométrie finale

1. Après validation de la phase A, créer la cornière avec `Miroir X`, `Miroir Y` désactivé et une rotation de `45°`.
2. Vérifier l'absence de saut entre l'aperçu et le corps final.
3. Vérifier les attributs `flip_x = true`, `flip_y = false` et `rotation_deg = 45`.
4. Recommencer avec un tube rectangulaire et les deux miroirs afin de vérifier le contour intérieur.

## Test 9 — Inspection d'une barre existante

Cette étape est exclusivement en lecture seule.

1. Arrêter puis exécuter le complément et vérifier la présence de `Profil acier V1.7.0` et `Inspecter un profil acier V1.7.0`.
2. Créer si nécessaire une cornière inégale avec ancrage `Haut gauche`, rotation `45°`, `Miroir X` activé et `Miroir Y` désactivé.
3. Ouvrir `Inspecter un profil acier V1.7.0` puis sélectionner le composant de cette barre.
4. Vérifier que le profil, la famille, le DXF, l'ancrage `TL`, la rotation `45°` et les deux états de miroir correspondent.
5. Vérifier `DXF disponible : Oui` et `Liaison squelette : OK`.
6. Fermer la commande et vérifier que l'historique, l'esquisse, le corps et le composant n'ont pas changé.
7. Recommencer en sélectionnant un composant ordinaire et vérifier qu'il est indiqué comme non reconnu.

## Test 10 — Matériau physique Fusion

Procéder d'abord sans créer de barre.

### Phase A — Menu uniquement

1. Arrêter puis exécuter le complément et vérifier que les deux commandes indiquent la V1.8.0.
2. Ouvrir `Profil acier V1.8.0` et vérifier la présence du menu `Matériau physique Fusion`.
3. Ouvrir le menu et vérifier que chaque ligne indique un matériau et sa bibliothèque source.
4. Vérifier qu'il ne s'agit plus d'un champ de texte libre et qu'aucun S235/S355 n'est inventé à partir de la famille du profil.
5. Choisir un matériau différent de celui proposé par défaut et noter exactement son libellé.
6. Sélectionner une ligne et vérifier que l'aperçu jaune fonctionne toujours ; le matériau ne doit pas modifier la géométrie de l'aperçu.
7. Annuler sans créer de barre et signaler la liste visible si elle paraît vide, incomplète ou ambiguë.

### Phase B — Enregistrement et inspection

1. Après validation de la phase A, créer une seule barre `IPE 100` avec le matériau noté.
2. Ouvrir la commande d'inspection et sélectionner cette barre.
3. Vérifier que `Matériau enregistré` et `Matériau lu sur le corps` concordent.
4. Vérifier `Affectation physique : OK` et un nombre de propriétés physiques strictement supérieur à zéro.
5. Vérifier également le même matériau par clic droit sur le corps ou le composant, puis `Matériau physique` dans Fusion.
6. Si l'espace Simulation est disponible, ouvrir `Matériaux de l'étude` et vérifier que la même matière est reconnue avant tout calcul.
7. Fermer l'inspection et vérifier qu'aucune géométrie n'a été modifiée.

## Test 11 — Nuances européennes créées automatiquement

Utiliser un nouveau document de conception paramétrique pour isoler ce test.

### Phase A — Création unique

1. Arrêter puis exécuter le complément et vérifier que les deux commandes indiquent la V1.9.7.
2. Vérifier qu'aucun message d'erreur concernant les propriétés physiques n'apparaît.
3. Ouvrir `Profil acier V1.9.7`, puis vérifier que le champ `Matériau physique Fusion` affiche déjà le S235JR du document actif.
4. Vérifier la présence exacte de `S235JR EN 10025-2 - t<=16 mm — Document actif`.
5. Vérifier la présence exacte de `S275JR EN 10025-2 - t<=16 mm — Document actif`.
6. Vérifier la présence exacte de `S355J2 EN 10025-2 - t<=16 mm — Document actif`.
7. Annuler, arrêter puis exécuter une seconde fois le complément dans le même document.
8. Rouvrir le menu et vérifier qu'il existe toujours exactement une ligne pour chaque nuance.

### Phase B — Trois profils comparables

1. Préparer trois lignes parallèles de même longueur.
2. Créer un `IPE 100` sur la première avec le matériau S235JR du document actif.
3. Créer un second `IPE 100` sur la deuxième avec le matériau S275JR du document actif.
4. Créer un troisième `IPE 100` sur la troisième avec le matériau S355J2 du document actif.
5. Inspecter chaque barre et vérifier que le matériau enregistré correspond à celui lu sur le corps avec `Affectation physique : OK`.
6. Ouvrir les propriétés des matériaux et contrôler `E = 210 GPa` et `nu = 0,30` pour les trois.
7. Contrôler les limites d'élasticité : `235 MPa` pour S235JR, `275 MPa` pour S275JR et `355 MPa` pour S355J2.
8. Si l'espace Simulation est disponible, ouvrir `Matériaux de l'étude` et vérifier que les trois matériaux sont acceptés sans avertissement jaune avant tout calcul.

## Test 12 — Catégorie et zone géographique

1. Arrêter puis exécuter le complément et vérifier que les deux commandes indiquent la V1.10.0.
2. Ouvrir `Profil acier V1.10.0`.
3. Vérifier `Catégorie : Zones géographiques` puis `Zone géographique : Europe`.
4. Vérifier que `IPE / 100` reste la sélection par défaut.
5. Choisir `HEA / 160`, sélectionner une ligne et vérifier que l'aperçu jaune reste correct.
6. Créer la barre puis l'ouvrir avec `Inspecter un profil acier V1.10.0`.
7. Vérifier `Catégorie : Zones géographiques`, `Zone géographique : Europe` et `DXF disponible : Oui`.
8. Inspecter si possible une barre créée avec une version antérieure et vérifier que son ancien chemin DXF reste disponible.

## Test 13 — Ajouter et supprimer un profil personnalisé

Utiliser pour ce premier essai une copie d'un DXF déjà validé, par exemple `IPE_100.dxf`, afin de tester le gestionnaire indépendamment de la qualité d'un nouveau dessin.

### Phase A — Ajout contrôlé

1. Arrêter puis exécuter le complément et vérifier la présence de `Profil acier V1.11.0`, `Inspecter un profil acier V1.11.0` et `Gérer les profils personnalisés V1.11.0`.
2. Ouvrir le gestionnaire, conserver l'action `Ajouter un profil DXF`, saisir la famille `Essais` et la désignation `IPE test 100`.
3. Cocher la confirmation des millimètres, puis choisir la copie de `IPE_100.dxf`.
4. Vérifier le rapport avant validation : `55 × 100 mm`, un contour fermé et un nombre d'entités strictement positif.
5. Valider l'ajout, fermer le gestionnaire puis ouvrir `Profil acier V1.11.0`.
6. Choisir `Catégorie : Personnalisés` et vérifier que le champ `Zone géographique` disparaît.
7. Choisir `Essais / IPE test 100`, sélectionner une ligne et contrôler l'aperçu jaune.
8. Créer la barre, mesurer `55 × 100 mm`, puis l'inspecter et vérifier `Catégorie : Personnalisés` et `DXF disponible : Oui`.

### Phase B — Suppression récupérable

1. Rouvrir le gestionnaire et choisir l'action `Supprimer un profil`.
2. Sélectionner `Essais IPE test 100` et vérifier que le rapport indique au moins une barre utilisatrice dans le document actif.
3. Valider et vérifier la présence de l'avertissement avant de confirmer.
4. Rouvrir `Profil acier` et vérifier que le profil supprimé n'est plus proposé.
5. Vérifier que la barre existante et son corps sont toujours présents et inchangés.
6. Inspecter cette barre et vérifier que son DXF source est maintenant signalé indisponible.
7. Vérifier sur disque que le DXF, ses métadonnées et `suppression.json` existent dans la corbeille locale ; ne pas les restaurer pendant ce premier test.

## Critères de validation

- aucune erreur dans le journal Fusion ;
- aperçu temporaire visible avant validation et absent de l'historique ;
- famille et section sélectionnables uniquement parmi les DXF présents ;
- catégorie `Zones géographiques` et zone `Europe` affichées avant la famille ;
- catégorie `Personnalisés` distincte, sans zone géographique visible ;
- ajout d'un DXF personnel sans modification du fichier source ;
- suppression limitée aux profils personnels, précédée d'un avertissement et conservée dans la corbeille locale ;
- neuf ancrages cliquables avec centre sélectionné par défaut ;
- un seul point rouge et huit points bleus ;
- aperçu et corps final placés sur le même ancrage ;
- aperçu et corps final orientés avec le même angle autour de cet ancrage ;
- miroirs X/Y indépendants et cumulables sans déplacement de l'ancrage ;
- esquisse créée par import direct du DXF sélectionné ;
- contours intérieurs conservés pour les profils creux ;
- une région de matière fermée et un corps unique par barre ;
- dimensions exactes ;
- section au milieu du chemin ;
- mise à jour après modification du squelette ;
- lignes droites et arcs traités comme chemins indépendants ;
- composants indépendants et noms prévisibles.
- inspection des barres sans modification de la géométrie ni de l'historique.
- matériau choisi dans une bibliothèque Fusion, réellement affecté au corps et relu avec le même identifiant.
- exactement une occurrence de chacune des trois nuances européennes dans le document actif après plusieurs lancements.

Tout écart doit être ajouté à `KNOWN_ISSUES.md` avant correction. Toute correction livrée doit apparaître dans `CHANGELOG.md`.
