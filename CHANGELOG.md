# Historique des versions

Toutes les évolutions livrées de `fusion-free-structure` sont consignées ici.

## [Non publié]

## [1.4.0] - 2026-08-16

### Ajouté

- grille visuelle `3 × 3` de neuf points d'ancrage cliquables ;
- points disponibles affichés en bleu et point actif affiché en rouge ;
- ancrage central `C` conservé comme choix par défaut ;
- déplacement immédiat de l'aperçu jaune autour du point sélectionné ;
- import final positionné avec le même ancrage, sans déplacement ni simplification du DXF source ;
- code de l'ancrage enregistré dans le composant créé ;
- calcul vérifié sur les neuf positions des 341 profils, soit 3 069 combinaisons.

### Validé dans Fusion

- affichage des neuf points, couleur bleue des positions disponibles et couleur rouge du point actif confirmés ;
- déplacement dynamique de l'aperçu confirmé pour les neuf positions ;
- correspondance sans saut entre l'aperçu et le corps final confirmée ;
- positionnement final validé sur un IPE, une cornière asymétrique et un tube creux ;
- dimensions, contours intérieurs, composant unique et corps unique confirmés par l'utilisateur.

## [1.3.1] - 2026-08-16

### Modifié

- nom du bouton généré depuis le manifeste, sous la forme `Profil acier V1.3.1` ;
- version exacte également affichée dans la fenêtre de commande et dans le journal Fusion ;
- attribut `extension_version` des nouvelles barres alimenté par la même source, afin d'éviter les versions divergentes.

### Validé dans Fusion

- affichage de `Profil acier V1.3.1` et de la version chargée confirmé par l'utilisateur.

## [1.3.0] - 2026-08-16

### Ajouté

- deux listes liées permettent de choisir d'abord la famille, puis la section disponible ;
- les listes sont générées depuis les 341 DXF réellement présents, sans catalogue recopié dans le code ;
- l'aperçu jaune change immédiatement avec le profil sélectionné ;
- l'import final, le nom du composant et les attributs de traçabilité utilisent le même DXF sélectionné ;
- le centre de la boîte géométrique du DXF devient l'ancrage `C`, sans modifier la géométrie source ;
- les lignes, arcs, cercles et polylignes DXF sont pris en charge par l'aperçu ;
- les contours intérieurs des tubes carrés, rectangulaires et ronds sont conservés ;
- contrôle automatisé de la géométrie et des contours des 341 profils.

### Validé dans Fusion

- chargement du complément et profil `IPE 100` sélectionné par défaut confirmés ;
- navigation dans toutes les familles et mise à jour de l'aperçu jaune confirmées ;
- création des profils pleins et des tubes creux confirmée, sans défaut signalé ;
- dimensions, extrusion et fonctionnement général confirmés par l'utilisateur.

## [1.2.0] - 2026-08-16

### Ajouté

- aperçu dynamique jaune semi-transparent pour chaque ligne ou arc sélectionné ;
- contour d'aperçu lu depuis le vrai DXF, sans import ni entité CAO pendant la commande ;
- suppression automatique de l'aperçu avant la création finale et lors de l'annulation ;
- maillage visuel isolé du DXF final afin que l'approximation d'affichage ne modifie jamais la section réelle.

### Validé dans Fusion

- apparition, mise à jour et remplacement de l'aperçu par le corps final confirmés par l'utilisateur ;
- couleur finale remplacée par le jaune demandé.

## [1.1.0] - 2026-08-16

### Ajouté

- sélection des arcs d'esquisse en plus des lignes droites ;
- création d'un IPE 100 cintré par balayage du DXF sur l'arc entier ;
- traçabilité généralisée avec `source_curve_token` et `source_curve_type` ;
- refus explicite des autres courbes d'esquisse pour limiter cette étape aux lignes et aux arcs.

### Validé dans Fusion

- création sur ligne et sur arc confirmée par l'utilisateur ;
- mise à jour dynamique du profil cintré confirmée.

## [1.0.1] - 2026-08-16

### Corrigé

- reconstruction manuelle de l'IPE 100 remplacée par l'import direct du fichier relatif `profiles/IPE/IPE_100.dxf` ;
- import exécuté par un événement différé compatible avec la limitation de l'API Fusion ;
- déclenchement de l'événement déplacé dans un thread de travail après le refus observé lors du premier essai réel ;
- contrôle automatique avant balayage : section fermée unique, dimensions `55 × 100 mm` et ancrage central `C` ;
- tests hors Fusion déplacés des coordonnées recopiées vers le contenu du vrai DXF.

### Validé dans Fusion

- import direct, fermeture du profil et extrusion confirmés par l'utilisateur ;
- problèmes `ISSUE-006` et `ISSUE-007` résolus.

### Documentation

- installation locale de la V1 confirmée ;
- blocage externe du pilotage automatique de la fenêtre Fusion consigné dans `KNOWN_ISSUES.md` ; aucun échec de l'extension n'est conclu tant que l'essai manuel n'a pas été lancé.

## [1.0.0] - 2026-08-16

### Ajouté

- première V1 technique de l'extension Fusion ;
- sélection multiple de lignes droites d'esquisse du composant racine ;
- création d'un composant indépendant par barre ;
- section exacte IPE 100, ancrage central `C`, rotation `0°` ;
- plan de section paramétrique à mi-longueur ;
- balayage sur la ligne complète pour conserver la dépendance au squelette ;
- attributs de traçabilité sur chaque composant créé ;
- bibliothèque publique de 341 profils DXF répartis dans 12 familles ;
- tests géométriques et contrôles de structure du dépôt ;
- protocole d'essai Fusion, registre des problèmes et feuille de route.

### Corrigé pendant la préparation

- manifeste aligné sur le produit Autodesk `Fusion` ;
- imports Python convertis en imports relatifs adaptés à un complément Fusion ;
- rayon et raccords exacts du contour IPE 100 conservés ;
- préparation du dépôt refaite par copie sélective après le refus d'une opération combinant copie et nettoyage.
- caches Python contenant les chemins locaux retirés du payload après le contrôle de sécurité ;
- contrôle automatique ajouté pour interdire tout bytecode dans le contenu publiable.
- fins de ligne figées pour conserver les DXF à l'identique dans Git et garder le code portable.

### Limites connues

- profil fixe IPE 100 ;
- ancrage et rotation fixes ;
- essai dynamique réel dans Fusion encore requis avant de déclarer la V1 stable.
