# Améliorations prévues

Les éléments sont ajoutés ici avant leur implémentation. Une amélioration terminée est retirée de cette liste uniquement lorsque sa livraison apparaît dans `CHANGELOG.md`.

## Prochaine étape de validation

- [ ] charger la V1 dans Fusion sur un document vierge ;
- [ ] créer une barre sur une ligne de 200 mm ;
- [ ] modifier la ligne à 300 mm et vérifier la mise à jour automatique ;
- [ ] créer deux barres à partir de deux lignes ;
- [x] créer une barre cintrée sur un arc et vérifier son fonctionnement dans Fusion ;
- [ ] vérifier l'arborescence, la section 55 × 100 mm et le corps unique.

## Interface profils

- [x] afficher les profils par famille puis par dimension ;
- [x] organiser les profils normalisés par catégorie puis par zone géographique ;
- [x] exposer la zone Europe sans modifier les 341 DXF existants ;
- [ ] ajouter une catégorie séparée `Personnalisés` ;
- [ ] permettre à l'utilisateur d'importer ses propres profils DXF dans cette catégorie ;
- [ ] contrôler avant import personnalisé les unités, les contours fermés, l'origine et le nommage ;
- [ ] afficher un aperçu visuel du profil ;
- [x] proposer neuf points d'ancrage cliquables ;
- [x] afficher les ancrages en bleu et l'ancrage actif en rouge ;
- [x] permettre une rotation réglable autour de l'ancrage sélectionné ;
- [x] permettre des miroirs X/Y indépendants autour de l'ancrage ;
- [x] produire un aperçu dynamique avant validation.
- [ ] valider dans Fusion l'inspection en lecture seule d'une barre existante, implémentée dans la V1.7.0 candidate ;
- [ ] transformer ensuite cette inspection en commande de modification contrôlée.
- [ ] valider dans Fusion le menu dynamique et l'affectation physique de la V1.8.0 candidate ;
- [ ] vérifier sur une barre test que Fusion relit le même matériau dans l'inspecteur et dans l'interface de matériau physique ;
- [ ] vérifier séparément la disponibilité des propriétés nécessaires au type de simulation envisagé.
- [x] créer automatiquement dans le document actif les nuances S235JR, S275JR et S355J2 de la première phase.
- [ ] valider dans Fusion la création unique et les valeurs physiques de la V1.9.0.
- [ ] comparer trois IPE 100 identiques en S235JR, S275JR et S355J2 dans une étude linéaire.
- [ ] ajouter les autres plages d'épaisseur et les nuances de tubes uniquement après cette validation.

## Géométrie et structure

- [x] généraliser aux 341 profils l'import DXF relatif d'abord validé sur l'IPE 100 ;
- [ ] prendre en charge les lignes appartenant à des sous-composants ;
- [ ] gérer une orientation de référence contrôlable ;
- [ ] ajouter des décalages ;
- [ ] prévoir les jonctions, coupes, grugeages et assemblages dans une phase séparée.

## Qualité

- [ ] choisir une licence publique ;
- [x] automatiser le contrôle de tous les DXF à chaque livraison ;
- [ ] ajouter des essais Fusion reproductibles pour chaque fonction importante.
- [ ] libérer les gestionnaires propres à une commande quand sa fenêtre est détruite afin d'éviter leur accumulation pendant une longue session ;
- [ ] définir une limite pratique ou un traitement par lots pour les très grandes sélections de lignes.
