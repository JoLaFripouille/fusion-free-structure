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

## Critères de validation

- aucune erreur dans le journal Fusion ;
- aperçu temporaire visible avant validation et absent de l'historique ;
- famille et section sélectionnables uniquement parmi les DXF présents ;
- esquisse créée par import direct du DXF sélectionné ;
- contours intérieurs conservés pour les profils creux ;
- une région de matière fermée et un corps unique par barre ;
- dimensions exactes ;
- section au milieu du chemin ;
- mise à jour après modification du squelette ;
- lignes droites et arcs traités comme chemins indépendants ;
- composants indépendants et noms prévisibles.

Tout écart doit être ajouté à `KNOWN_ISSUES.md` avant correction. Toute correction livrée doit apparaître dans `CHANGELOG.md`.
