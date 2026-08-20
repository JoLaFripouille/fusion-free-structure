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

- [x] regrouper toutes les commandes dans un onglet Fusion dédié avec panneaux Créer, Modifier, Assemblages et Paramètres ;
- [x] afficher les profils par famille puis par dimension ;
- [x] organiser les profils normalisés par catégorie puis par zone géographique ;
- [x] exposer la zone Europe sans modifier les 341 DXF existants ;
- [x] ajouter une catégorie séparée `Personnalisés` ;
- [x] permettre à l'utilisateur d'importer ses propres profils DXF dans cette catégorie ;
- [x] contrôler avant import personnalisé les unités, les contours fermés, l'origine logique par enveloppe et le nommage ;
- [x] permettre la suppression récupérable des profils personnels sans toucher aux profils normalisés ;
- [ ] ajouter une commande de restauration depuis la corbeille locale ;
- [ ] accepter d'autres versions de DXF ou d'autres unités uniquement après une conversion explicitement validée ;
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
- [x] détecter une barre déjà liée au chemin et permettre son remplacement contrôlé ;
- [ ] prendre en charge les lignes appartenant à des sous-composants ;
- [ ] gérer une orientation de référence contrôlable ;
- [ ] ajouter des décalages ;
- [x] ajouter une première jonction droite : principale intacte, secondaire coupée à l'enveloppe et jeu réglable.
- [x] accepter une barre secondaire cintrée en coupant normalement à sa tangente d'extrémité.
- [ ] permettre la suppression contrôlée d'une jonction depuis une commande dédiée.
- [x] prendre en charge plusieurs jonctions, notamment une à chaque extrémité d'une même barre.
- [x] ajouter un premier mode de coupe d'onglet qui coupe explicitement deux barres droites suivant un plan commun.
- [x] adapter la jonction ajustée aux angles non droits à partir des axes réels.
- [x] prolonger automatiquement une barre séparée du plan et couper une barre qui le chevauche.
- [ ] étendre la coupe d'onglet aux cas cintrés après validation du mode droit.
- [x] ajouter un premier aperçu non destructif du double grugeage pour une secondaire IPE à 90°.
- [x] valider à `90°` l'aperçu V1.17.1 avec coupe sur l'âme et prolongement de la principale.
- [x] créer le premier double grugeage IPE réel à `90°`, y compris le prolongement nécessaire de la principale et la coupe droite sur son âme.
- [x] valider la création V1.18.0 dans Fusion sur une principale longue, une principale trop courte et les deux extrémités d'une même secondaire.
- [ ] compléter la validation V1.18.0 sur plusieurs tailles, ancrages, rotations et miroirs.
- [x] généraliser le moteur de double grugeage aux secondaires HEA et HEB.
- [x] calculer le plan d'âme et les volumes de grugeage pour les angles non parallèles.
- [x] corriger le début des retraits de semelles pour qu'il suive la face extérieure oblique de la principale.
- [x] valider la V1.19.1 corrigée dans Fusion sur le raccord oblique signalé ; compléter ensuite les essais séparés à `30°` et `45°`.
- [x] généraliser le calcul et la création aux quatre combinaisons cornière/té dans la V1.20.0.
- [x] limiter le retrait droit des cornières/tés à leur épaisseur et ajouter séparément le dégagement arrondi du congé principal dans la V1.20.1, sans modifier les IPE/HEA/HEB.
- [x] séparer dans la V1.20.2 le jeu sous l'âme secondaire du jeu autour du congé principal, avec des champs propres aux cornières/tés.
- [x] ajouter dans la V1.21.0 une fenêtre `Paramètres > Valeurs par défaut`, persistée localement et organisée par opération et groupe de profils.
- [x] ajouter dans la V1.22.0 un aperçu non destructif de deux cornières égales autour de l'âme secondaire, limité aux IPE/HEA/HEB droits à `90°`.
- [x] valider dans Fusion la position des deux cornières V1.22.0 sur les deux faces de l'âme secondaire et la face de l'âme principale.
- [x] créer dans la V1.23.0 deux composants de cornière indépendants et les perçages paramétrés alignés dans les deux âmes, à la demande de l'utilisateur.
- [x] valider dans Fusion la création et les perçages V1.23.6 avant d'ajouter les boulons.
- [x] prototyper dans la V1.24.0 des boulons géométriques comme composants indépendants ; solution remplacée avant validation Fusion.
- [x] remplacer dans la V1.24.1 ce prototype par la présélection des six perçages et l'ouverture de la commande native `Insérer une attache`.
- [x] corriger dans la V1.24.2 le refus de planification en déclenchant l'événement personnalisé hors de l'événement de commande JHR.
- [ ] valider dans Fusion que les six arêtes sont acceptées ensemble et que la bibliothèque native dimensionne correctement les quatre axes principaux et les deux axes secondaires.
- [ ] tester ensuite séparément l'ajout natif des écrous et rondelles sur les attaches créées.
- [ ] intégrer le jeu entre secondaire et principale ainsi que les distances aux bords uniquement après définition des valeurs souhaitées par l'utilisateur ou le calculateur structure.
- [ ] ajouter de nouveaux onglets de paramètres uniquement lorsque de nouvelles catégories de réglages auront été validées.
- [ ] valider séparément dans Fusion cornière→cornière, cornière→té, té→cornière et té→té avant d'ajouter d'autres profils ouverts.
- [ ] ajouter séparément les platines et les autres assemblages composés.

## Qualité

- [ ] choisir une licence publique ;
- [x] automatiser le contrôle de tous les DXF à chaque livraison ;
- [ ] ajouter des essais Fusion reproductibles pour chaque fonction importante.
- [ ] libérer les gestionnaires propres à une commande quand sa fenêtre est détruite afin d'éviter leur accumulation pendant une longue session ;
- [ ] définir une limite pratique ou un traitement par lots pour les très grandes sélections de lignes.
