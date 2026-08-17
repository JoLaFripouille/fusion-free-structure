# Historique des versions

Toutes les évolutions livrées de `fusion-free-structure` sont consignées ici.

## [Non publié]

## [1.9.1] - En validation

### Corrigé

- suppression de l'appel à `FusionUnitsManager.convert` pour les propriétés de matériau, celui-ci refusant la chaîne d'unité de densité au démarrage de la V1.9.0 ;
- conversion contrôlée vers l'unité réellement déclarée par chaque propriété Fusion pour la densité et les contraintes mécaniques ;
- prise en charge explicite des unités usuelles `kg/m³`, `kg/cm³`, `kg/mm³`, `g/cm³`, `g/mm³`, `Pa`, `kPa`, `MPa`, `GPa`, `N/mm²`, `psi` et `ksi` ;
- tests ajoutés pour la densité en `kg/m³` et `kg/mm³`, le module de Young en `Pa` et la limite d'élasticité en `N/mm²`.

## [1.9.0] - En validation

### Ajouté

- vérification idempotente, au démarrage du complément, de deux matériaux européens dans le document Fusion actif ;
- création automatique de `S235JR EN 10025-2 - t<=16 mm` et `S355J2 EN 10025-2 - t<=16 mm` lorsqu'ils sont absents ;
- propriétés destinées au premier essai linéaire : masse volumique, module de Young, coefficient de Poisson, limite d'élasticité et résistance minimale à la traction ;
- contrôle des valeurs après écriture et suppression de toute copie incomplète en cas d'échec ;
- refus sans écrasement lorsqu'un matériau existant porte le nom réservé mais possède des valeurs différentes ;
- présence des deux matériaux du document actif dans le menu de création des barres ;
- nouvelle vérification à l'ouverture de la commande pour les documents ouverts après le démarrage du complément ;
- tests de création unique, de non-duplication, de conservation des matériaux conformes et de refus des conflits.

### Valeurs de cette première phase

- propriétés communes : `rho = 7 850 kg/m³`, `E = 210 GPa`, `nu = 0,30` ;
- S235JR, `t <= 16 mm` : `ReH min = 235 MPa`, `Rm min = 360 MPa` ;
- S355J2, `t <= 16 mm` : `ReH min = 355 MPa`, `Rm min = 470 MPa` ;
- source de nuance : EN 10025-2:2019 ; les certificats matière restent nécessaires pour une justification réelle.

### Limite connue

- l'API publique Fusion permet de copier un matériau dans le document actif mais pas de l'ajouter à une bibliothèque globale ; la V1.9.0 vérifie donc chaque document au démarrage ou à l'ouverture de la commande.

### À valider dans Fusion

- première exécution : deux créations et aucune erreur ;
- seconde exécution dans le même document : zéro création et aucun doublon ;
- présence des deux nuances sous la source `Document actif` dans le menu ;
- création de deux IPE 100 identiques, l'un en S235JR et l'autre en S355J2 ;
- reconnaissance des deux matériaux sans avertissement dans `Matériaux de l'étude` avant tout calcul.

## [1.8.0] - En validation

### Ajouté

- menu `Matériau physique Fusion` produit directement depuis les bibliothèques chargées dans Fusion ;
- affichage du nom exact du matériau et de sa bibliothèque source ;
- inventaire limité aux matériaux acier détectés dans leur nom ou leur description et possédant des propriétés physiques ;
- sélection par identifiants internes uniques de la bibliothèque et du matériau, sans dépendre d'un nom potentiellement dupliqué ;
- affectation réelle du matériau choisi au corps créé, puis relecture immédiate par Fusion ;
- attributs persistants du matériau demandé et du matériau effectivement appliqué ;
- contrôle dans l'inspection du matériau lu sur le corps, de son identifiant et du nombre de propriétés physiques ;
- compatibilité de lecture avec une ancienne barre ne possédant aucun attribut matière ou seulement l'ancien texte `steel_grade` ;
- tests indépendants du catalogue, des doublons de noms, de la résolution par identifiant et de la traçabilité.

### Important

- aucune correspondance S235/S355 n'est déduite de la famille du profil ;
- une nuance absente des bibliothèques chargées par Fusion n'est ni inventée ni remplacée silencieusement ;
- la présence d'un matériau dans Fusion et de propriétés physiques ne remplace pas la vérification de sa fiche pour le type exact de simulation envisagé.

### À valider dans Fusion

- contenu réel du menu avec les bibliothèques chargées sur la machine d'essai ;
- création d'une seule barre avec un matériau choisi dans ce menu ;
- concordance entre le matériau enregistré et celui réellement relu sur le corps ;
- état `Affectation physique : OK` dans la commande d'inspection ;
- visibilité du même matériau dans l'interface de matériau physique et, si disponible, dans une étude de simulation Fusion.

## [1.7.0] - Candidat intermédiaire non publié

### Ajouté

- nouvelle commande distincte `Inspecter un profil acier V1.7.0` ;
- sélection en lecture seule d'un composant créé par l'extension ;
- affichage du profil, de la famille, du DXF source, de l'ancrage, de la rotation et des miroirs enregistrés ;
- contrôle de la présence du DXF dans la bibliothèque relative ;
- résolution du jeton Fusion afin de vérifier que la ligne ou l'arc du squelette existe toujours ;
- prise en charge des anciennes barres possédant seulement `source_line_token` et aucun attribut de miroir ;
- refus explicite des composants ordinaires ou des attributs incohérents ;
- aucune suppression, reconstruction ou modification de géométrie dans cette première phase.

### À valider dans Fusion

- présence des deux commandes V1.7.0 dans la barre d'outils ;
- sélection d'une barre depuis le modèle ou l'arborescence ;
- concordance des informations affichées avec les choix utilisés à la création ;
- état `OK` de la liaison au squelette ;
- absence totale de modification après fermeture de la commande.

La fonction d'inspection est reprise sans modification géométrique dans la V1.8.0 candidate.

## [1.6.0] - 2026-08-16

### Ajouté

- deux boutons à état `Miroir X` et `Miroir Y`, indépendants et cumulables ;
- mise à jour immédiate de l'aperçu jaune lors de chaque inversion ;
- miroirs appliqués autour du point d'ancrage avant la rotation choisie ;
- matrice d'orientation commune au calcul de l'aperçu et à l'esquisse DXF finale ;
- états enregistrés dans les attributs `flip_x` et `flip_y` de chaque composant ;
- icônes locales X/Y, sans ressource externe ni chemin propre à la machine ;
- tests des deux axes, de leur combinaison et de l'ordre miroir puis rotation.

### Validé dans Fusion

- affichage et état des deux boutons confirmés ;
- miroirs X et Y séparés ainsi que leur combinaison confirmés sur l'aperçu ;
- maintien du point d'ancrage pendant les miroirs et la rotation confirmé par l'utilisateur.
- correspondance entre aperçu, esquisse DXF et corps final confirmée ;
- création finale testée sur l'ensemble des familles, y compris les tubes creux, sans défaut signalé ;
- rotation, ancrage et miroirs combinés confirmés sur les profils testés.

## [1.5.0] - 2026-08-16

### Ajouté

- champ d'angle en degrés dans la fenêtre de commande, avec `0°` par défaut ;
- rotation dynamique de l'aperçu jaune autour du point d'ancrage actif ;
- rotation de l'esquisse DXF finale autour de sa propre origine après le contrôle de l'échelle et de l'ancrage ;
- même valeur d'angle transmise à l'aperçu et à la création différée ;
- angle réellement demandé enregistré dans l'attribut `rotation_deg` du composant ;
- tests isolés du pivot autour de l'origine, notamment avec l'ancrage haut gauche d'un IPE 100.

### Validé dans Fusion

- présence du champ d'angle et affichage de la V1.5.0 confirmés ;
- rotation dynamique de l'aperçu autour de l'ancrage confirmée par l'utilisateur.
- correspondance entre aperçu et géométrie finale confirmée pendant la validation V1.6.0 ;
- raccords, contours fermés et vides intérieurs conservés après rotation.

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
