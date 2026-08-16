# Protocole d'essai Fusion — V1

Effectuer l'essai dans un nouveau document sans donnée de production.

Lors d'un import manuel d'un DXF de la bibliothèque, sélectionner explicitement les millimètres : le format R12 ne contient pas de champ `$INSUNITS`.

## Test 1 — Une barre

1. Créer un nouveau modèle avec l'historique de conception activé.
2. Dans le composant racine, créer une esquisse sur le plan XY.
3. Tracer une ligne horizontale contrainte à `200 mm`, puis terminer l'esquisse.
4. Lancer **Profil acier V1** et sélectionner la ligne.
5. Valider la commande.
6. Attendre le message confirmant que la barre a été créée depuis le DXF ; l'import est volontairement exécuté juste après la fermeture de la commande.
7. Vérifier la présence d'un composant `BARRE_IPE100_001` contenant un plan, une esquisse DXF, un balayage et un corps.
8. Ouvrir l'esquisse de section et vérifier que son contour correspond exactement au DXF source, avec quatre raccords corrects.
9. Mesurer la section : largeur `55 mm`, hauteur `100 mm`.
10. Mesurer la barre : longueur `200 mm`.

## Test 2 — Mise à jour paramétrique

1. Modifier la longueur de la ligne du squelette de `200 mm` à `300 mm`.
2. Terminer l'esquisse et laisser Fusion recalculer.
3. Vérifier que la barre mesure `300 mm` et que sa section reste `55 × 100 mm`.
4. Vérifier qu'aucun nouveau composant ou corps parasite n'est apparu.

## Test 3 — Sélection multiple

1. Ajouter une deuxième ligne droite non colinéaire au squelette.
2. Relancer la commande et sélectionner deux lignes encore non traitées.
3. Vérifier qu'un composant indépendant est créé pour chacune.

## Critères de validation

- aucune erreur dans le journal Fusion ;
- esquisse créée par import direct de `profiles/IPE/IPE_100.dxf` ;
- un profil fermé et un corps unique par barre ;
- dimensions exactes ;
- section au milieu du chemin ;
- mise à jour après modification du squelette ;
- composants indépendants et noms prévisibles.

Tout écart doit être ajouté à `KNOWN_ISSUES.md` avant correction. Toute correction livrée doit apparaître dans `CHANGELOG.md`.
