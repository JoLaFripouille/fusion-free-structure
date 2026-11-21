# Améliorations prévues

Les éléments sont ajoutés ici avant leur implémentation. Une amélioration terminée est retirée de cette liste uniquement lorsque sa livraison apparaît dans `CHANGELOG.md`.

## Demandes en cours sur Structure JHR

Les cases cochées correspondent à un essai réalisé. Le journal des versions précise ce qui a été installé dans Fusion.

**Structure JHR 1.30.1.** Dix-sept modèles à platines et 263 tests réussis.

### Tableau d’avancement

| Lot | État | Preuve ou prochain point |
|---|---|---|
| Profilés, coupes et grugeage | Essais Fusion réussis | Longueurs et angles modifiés sur squelette. Vérifier ensuite le déplacement d’un nœud et le remplacement d’une section. |
| Pieds, abouts, plat d’âme et cornières | Essais Fusion réussis | Cales fourchettes, platines déportées, goussets, perçages et boulons contrôlés sur les montages d’essai. |
| Éclissage, faîtage et contreventement | Essais Fusion réussis | Éclisses sur une face, deux faces ou avec couvre-joints. Contrôles UPE 120 avec ailes et UPN 120 sur âme. Faîtages et gousset sur deux sections de cornière. |
| Portique de démonstration | Vérifié dans `Sans nom` | Deux abouts d’arbalétrier, croisement en X et quatre attaches de bout. Dégagement vérifié près des jarrets. |
| Boulonnerie et RIVKLE | Essais Fusion réussis | Trois têtes RIVKLE posées sur M6 et deux essais de pose avec vis et rondelle. |
| Recalcul des assemblages | Pieds, plats d’âme, abouts droits et éclissages vérifiés dans Fusion | Déplacement du nœud ou de la paire éclissée, changement des longueurs, retour aux cotes initiales. Changement de jeu détecté par l’inspecteur. Étendre aux autres montages et aux changements de section. |
| Garde-corps et nouveaux goussets | Essais Fusion réussis | Goussets évasés sur une à trois cornières. Garde-corps en Y et en Z, avec montage latéral, raccord palier-rampant, plinthe et têtes biseautées. Perçages acier et tiges d’ancrage vérifiés précédemment. |
| Interface et icônes | Ruban enregistré dans Fusion | Pictogrammes révisés et ressources associées. Parcours complet du formulaire à vérifier. |

### 1. Coupes et raccords existants

- [x] Faire suivre les profilés et les coupes d’onglet après modification des longueurs et des angles du squelette.
- [x] Garder le bon solide et le jeu réel à la jonction droite. Contrôler le grugeage et la pose des cornières sur une variation de longueur.
- [x] Vérifier le déplacement du nœud et le changement de section compatible sans perdre le composant. Le remplacement contrôle les raccords liés et revient à la section précédente si les pièces demandent une reprise.
- [ ] Étendre la reprise aux montages historiques et aux changements qui imposent de recalculer les dimensions des tôles ou le nombre de trous.

### 2. Assemblages, platines et boulonnerie

- [x] Pieds de poteau I/H, tube et cornière, avec variantes de platine déportée et chanfreinée. Cales fourchettes à deux demi-oblongs ouverts par cale et goussets extérieurs en option sur le pied I/H.
- [x] About poutre-poteau côté aile, avec ou sans jarret. Huit boulons sur le jarret par défaut, quatre au niveau de l’IPE et quatre au niveau du jarret. Retrait haut de 5 mm, chanfrein de soudure de 20 mm et raidisseurs réglables.
- [x] Doubles cornières avec proposition de cotes selon la place et les rondelles. Plat d’âme soudé sur la première poutre et boulonné à la seconde, quatre boulons par défaut.
- [x] Deux secondaires opposées partagent les traversants. Sur l’essai IPE 240 après grugeage, quatre cornières 60 × 60 × 6 de 178,4 mm et seize M16 × 45 dont huit communs à la principale.
- [x] Éclissage d’âme avec une tôle de l’un ou l’autre côté, ou deux tôles. Couvre-joint en option sur l’aile supérieure ou sur les deux ailes. Essais sur IPE.
- [x] Jarrets de faîtage inférieurs, ou inférieurs et supérieurs. Coupes, platines et boulons essayés sur un faîtage symétrique.
- [x] Angles vifs, chanfreinés ou arrondis sur les platines rectangulaires, avec contrôle du débord des trous.
- [x] Gousset central sur quatre diagonales. Essai Fusion de référence sur deux cornières 60 × 60 × 6 et deux 70 × 70 × 7, avec huit perçages et huit boulons. Prévoir la cornière en premier pour les prochains contreventements.
- [x] Gousset d’extrémité sur aile ou âme avec déport réglable. Jeux d’about vérifiés dans Fusion à 5 et 20 mm après prolongement et recoupe, avec conservation de l’autre bout.
- [ ] Générer le contreventement depuis un rectangle d’esquisse lié aux poteaux. Choisir la section, inverser chaque cornière, régler les épaisseurs des goussets et le jeu d’about. Faire suivre les coupes, les goussets, les perçages et la visserie après modification du rectangle.
- [ ] Étendre le recalcul de l’auto-contreventement depuis deux faces aux groupes suivis d’autres opérations dans l’historique.
- [ ] Identifier les tôles à découper (platines, éclisses, goussets et raidisseurs) et leur face de référence pour exporter les contours, rayons et trous en DXF pour le laser.
- [x] Étendre l’éclissage aux âmes UPE/UPN et aux ailes parallèles des UPE en mesurant les congés dans le DXF. Essais UPE 120 et UPN 120.
- [x] Couvre-joints UPN avec contreplaques biaises et goussets sur une à trois cornières. Croisement en X à partir de deux cornières continues.
- [x] Ajouter les tiges d’ancrage droites et les platines de préscellement aux variantes de pied.

### 3. Fixations

- [x] Boulonnerie JHR sur trou rond ou oblong, détection des doublons, longueur selon les faces d’appui.
- [x] Tête fraisée avec empreinte hexagonale et bord cylindrique. Vis H dans un taraudage ISO, avec ou sans filets physiques.
- [x] Ajouter les vis à tête bombée et cylindrique six pans creux. Solides vérifiés pour tous les diamètres proposés et pose M6 vérifiée dans Fusion, sur trou rond et oblong.
- [x] RIVKLE M4 à M10, à têtes plate, fraisée ou réduite, avec référence, diamètre et bourrelet côté aveugle. Pose des trois têtes essayée sur M6 avec préparation existante.
- [x] Préparer un avant-trou existant au diamètre catalogue. Fusion a vérifié l’agrandissement d’un avant-trou pour un M6 à tête plate et la préparation d’un M6 à tête fraisée.
- [x] Poser une vis et sa rondelle avec le RIVKLE. Contrôler la longueur, le dépassement et le doublon.
- [x] Contrôler la présence du bourrelet derrière la paroi et du chanfrein arrière sur les 42 références et sur un M6 posé dans Fusion.
- [ ] Examiner les fichiers STEP par référence pour les modèles détaillés des RIVKLE.
- [x] Vérifier les possibilités d’« Insérer une attache » côté Autodesk. La documentation expose la lecture des pièces du catalogue déjà insérées. L’ouverture native reste proposée dans les cornières, et le MCP peut générer la boulonnerie JHR.

### 4. Garde-corps

- [x] Retrouver les règles JHR Advance Steel et les cas d’essai pour la pose à la française et à l’anglaise, l’appui réel, le rampant et le poteau à la jonction de deux supports.
- [x] Reprendre le calcul Fusion Fabrication pour la pose sur appui acier, le montage latéral, le raccord palier-rampant et la représentation des ancrages béton.
- [x] Reprendre la tête biseautée des poteaux plats et la plinthe d’une mezzanine. Contrôler la génération avec Y ou Z comme verticale.
- [x] Tronçonner au droit d’un poteau industriel, en deux demi-poteaux ou avec plat adjacent. La coupe de la main courante est normale au tube et les autres pièces suivent le plan des plats.
- [x] Garde-corps barreaudé en poses française et anglaise. Essais carrés et ronds dans Fusion, avec un vide horizontal maximal mesuré de 98,22 mm.
- [ ] Priorité du prochain lot. Ajouter la commande Jonction de main courante avec sélection des deux tubes, mesure des extrémités et création du raccord adapté.

### 5. Interface et diagnostic

- [x] Mettre les types d’assemblage, les champs et les unités dans un catalogue utilisé par le ruban et le MCP. Documenter où intervenir pour la géométrie, les perçages, la pose et les erreurs Fusion.
- [x] Refaire les pictogrammes en vue isométrique, dont le pied avec goussets à l’extérieur des ailes et le jarret sous poutre.
- [x] Nommer les profils des assemblages et ranger les boulons par tête, diamètre et longueur. Replier les nouvelles créations dans leur groupe d’historique.
- [ ] Vérifier l’ouverture et la navigation du formulaire depuis le ruban, puis compléter les aperçus cotés par type.
- [x] Monter le portique d’essai contreventé avec les entrées JHR, y compris les abouts d’arbalétrier et les quatre attaches d’extrémité.

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
- [x] tracer l'échec de la sonde automatique V1.24.3 pendant le chargement asynchrone de `FusionFastenersCommand`.
- [x] retirer entièrement cette sonde dans la V1.24.4 et revenir à l'ouverture native sûre.
- [x] centrer dans la V1.24.5 les doubles cornières sur la hauteur libre réelle de l'âme secondaire, indépendamment de l'ancrage DXF.
- [x] remplacer dans la V1.25.0 TEST la station numérique du grugeage par une référence directe au point d'extrémité du squelette et aux plans médians des barres.
- [x] tester dans la V1.25.1 une coupe directe du côté extérieur, puis la rejeter après la déformation constatée dans Fusion.
- [x] restaurer dans la V1.25.2 HOTFIX la méthode de grugeage géométriquement stable.
- [x] isoler visuellement l'inversion simultanée de `PLAN_DEBUT_GRUGEAGE` et `PLAN_COUPE_AME_PRINCIPALE`, puis les rattacher aux faces principales dans la V1.25.3 TEST.
- [ ] valider dans Fusion la mise à jour d'un grugeage IPE neuf après une variation de longueur à direction constante.
- [ ] étendre ensuite le recalcul au changement d'angle, puis aux jonctions droites, coupes d'onglet et assemblages composés.
- [ ] essayer manuellement `Toolkit.cmdDialog` une seule fois après chargement complet, sans utiliser `UI.CurrentCommandInfo`.
- [ ] analyser les identifiants éventuellement exposés avant d'autoriser un unique essai de remplissage automatique.
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
