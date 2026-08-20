# Historique des versions

Toutes les évolutions livrées de `fusion-free-structure` sont consignées ici.

## [Non publié]

## [1.16.3] - En validation

### Corrigé

- détection de la couverture insuffisante de la barre principale dans une jonction ajustée située près de son extrémité ;
- projection de la section réelle de la barre secondaire jusqu'au plan de contact, en tenant compte de son angle, de son orientation et de son ancrage ;
- prolongement automatique de la seule extrémité principale trop courte avant l'ajustement de la secondaire ;
- contrôle après création que la nouvelle face principale couvre effectivement toute la largeur requise ;
- indication séparée des prolongements principal et secondaire dans le rapport de la commande.

## [1.16.2] - En validation

### Corrigé

- suppression de l'hypothèse selon laquelle le sens positif d'une extrusion de face correspond toujours à la direction d'approche mondiale de la barre ;
- essai contrôlé des deux directions d'extrusion lorsque Fusion oriente différemment la surface plane interne ;
- nouvelle validation sur la face d'extrémité réellement obtenue : tous ses points doivent avoir dépassé le plan avant que la séparation soit autorisée ;
- suppression immédiate d'une tentative orientée dans le mauvais sens, sans laisser de fonction parasite dans l'historique ;
- rétablissement des rôles explicites « Barre principale » et « Barre secondaire » pour la jonction ajustée ; l'onglet conserve deux barres symétriques sans hiérarchie.

### Diagnostic Fusion

- la commande chargée dans le document signalé a été contrôlée directement : `Jonctions acier V1.16.1` était bien active ;
- les semelles partageaient la même diagonale, ce qui confirme la position du plan et localise le défaut dans le sens du prolongement du corps.

## [1.16.1] - En validation

### Corrigé

- correction de l'onglet incomplet lorsque les profils sont ancrés à l'axe : un chevauchement partiel avec le plan ne signifie plus que toute la face d'extrémité l'a dépassé ;
- calcul du prolongement sur tous les points de la face d'extrémité, aussi bien pour un espace initial que pour un chevauchement partiel ;
- absence de prolongement lorsque toute la face se trouve déjà au-delà du plan ;
- conservation du même plan de preview et du même plan de coupe : seul le volume temporairement prolongé est corrigé avant séparation.

### Validation ciblée

- cadre à l'axe avec quatre onglets : chaque coin doit être fermé sur toute la largeur du profil ;
- cadre décalé vers l'extérieur : le prolongement doit également combler l'espace avant la coupe ;
- cas déjà suffisamment traversant : aucune fonction de prolongement inutile ne doit être créée.

## [1.16.0] - En validation

### Corrigé

- suppression de l'hypothèse explicite d'un angle droit dans la jonction ajustée ;
- calcul du plan à partir de l'axe de référence et de la tangente réelle de la barre à ajuster, pour tout angle non parallèle supérieur à `5°` ;
- recherche de l'enveloppe sur les arêtes réelles du profil de référence, y compris les arcs, sans laisser la longueur de la barre déplacer le plan ;
- même point et même normale utilisés par la prévisualisation et par la fonction Fusion finale, avec contrôle bloquant si Fusion reconstruit un autre plan ;
- remplacement du drapeau unique `joint_type` par des enregistrements `operation_0001`, `operation_0002`, etc., contenant chacun l'extrémité concernée ;
- suppression du refus global d'une barre possédant déjà une jonction ;
- libellés neutres `Barre 1` et `Barre 2` pour l'onglet, les deux corps restant traités symétriquement ;
- classement géométrique initial en `chevauchement`, `déjà au plan`, `espace` ou `mauvais côté` ;
- prolongement paramétrique de la face d'extrémité avant séparation lorsqu'un ancrage laisse un espace entre le corps et le plan ;
- conservation directe de la partie intérieure lorsque les profils se chevauchent, sans exiger un contact préalable entre les solides.

### Traçabilité

- chaque opération mémorise son type, l'indice d'extrémité, l'autre barre, l'angle, le jeu, l'état initial et la longueur de prolongement ;
- les anciens attributs V1.12–V1.15 sont ignorés comme verrous et restent conservés pour ne pas altérer les documents existants ;
- toute erreur pendant une opération symétrique retire les fonctions et enregistrements déjà créés sur les deux composants.

### À valider dans Fusion

- jonctions ajustées à `30°`, `60°`, `90°` et `120°` ;
- deuxième jonction sur l'extrémité opposée d'une barre déjà traitée ;
- deux onglets successifs sur les deux extrémités d'une même barre ;
- profils décalés vers l'extérieur avec espace initial, puis profils centrés avec chevauchement ;
- superposition exacte entre le plan orange et le plan final dans les plans XY, XZ et YZ.

## [1.15.0] - En validation

### Ajouté

- menu `Type de jonction` dans la commande renommée `Jonctions acier` ;
- mode `Coupe d'onglet symétrique` pour deux barres droites jointes par leurs extrémités ;
- calcul du plan bissecteur commun indépendamment du sens de dessin des deux lignes ;
- création paramétrique, dans chaque composant, de deux plans normaux aux chemins, de leur axe d'intersection et du plan d'onglet angulaire ;
- séparation puis retrait de l'excédent sur les deux corps ;
- aperçu orange et rapport explicite avant de modifier les deux barres ;
- traçabilité réciproque de l'onglet sur les deux composants.

### Conservé

- le mode `Coupe droite sur la principale` reste sélectionné par défaut et conserve le jeu réglable ;
- la coupe droite sur une secondaire cintrée reste disponible sans modification de son fonctionnement.

### Limité pour ce premier essai

- l'onglet accepte uniquement deux barres droites dont les extrémités se rejoignent à `1 mm` près ;
- aucun jeu d'onglet, aucune barre cintrée et aucune jonction déjà existante ne sont acceptés dans ce mode ;
- si la seconde coupe échoue, les fonctions déjà créées sur la première barre sont supprimées avant d'afficher l'erreur.

### À valider dans Fusion

- les deux tubes rectangulaires obliques du cas signalé : aperçu orange, bouton `OK` actif puis coupe des deux corps sur un même plan ;
- angles aigus et obtus, ordre de sélection inversé et lignes dessinées en sens inverse ;
- mise à jour des deux onglets après déplacement raisonnable du point commun du squelette.

## [1.14.0] - En validation

### Ajouté

- prise en charge d'une barre secondaire créée sur un arc dans la commande `Jonction droite` ;
- lecture de la tangente exacte de l'arc à l'extrémité raccordée ;
- plan paramétrique normal au chemin secondaire placé à la bonne extrémité, puis décalé jusqu'à l'enveloppe de la barre principale ;
- affichage du type de chemin secondaire dans le rapport de la commande.

### Sécurisé

- barre principale encore limitée à un chemin droit pour que la recherche de son enveloppe reste fiable ;
- coupe droite limitée aux jonctions perpendiculaires à `1°` près ; les angles obliques sont refusés et orientés vers la future coupe d'onglet ;
- les arcs restent exclus du mode principal tant que la localisation exacte de leur enveloppe au point de contact n'est pas validée.

### À valider dans Fusion

- arc secondaire dont l'extrémité et la tangente rejoignent perpendiculairement une barre principale droite ;
- aperçu orange normal à la tangente, puis coupe réelle au même emplacement ;
- jeu nul et jeu de `2 mm` ;
- conservation du balayage cintré sur toute la partie restante.

## [1.13.0] - En validation

### Modifié

- création d'un onglet Fusion dédié `STRUCTURE JHR` dans l'espace de travail Conception ;
- regroupement de `Profil acier` et `Gérer les profils personnalisés` dans le panneau `CRÉER` ;
- regroupement de `Jonction droite` et `Inspecter un profil acier` dans le panneau `MODIFIER` ;
- retrait des quatre boutons des panneaux généraux de Fusion afin d'éviter les doublons et de rendre l'extension plus facile à retrouver ;
- suppression propre des deux panneaux puis de l'onglet lorsque le complément est arrêté.

### À valider dans Fusion

- présence d'un seul onglet `STRUCTURE JHR` après l'arrêt puis l'exécution du complément ;
- présence des quatre boutons dans leur groupe respectif et absence dans les anciens menus généraux ;
- disparition complète de l'onglet à l'arrêt, puis recréation unique à l'exécution suivante.

## [1.12.0] - En validation

### Ajouté

- nouvelle commande séparée `Jonction droite V1.12.0` avec sélection explicite d'une barre principale et d'une barre secondaire ;
- aperçu orange semi-transparent du plan de coupe, recalculé lors d'un changement de barre ou de jeu ;
- coupe de la barre secondaire à l'enveloppe extérieure de la barre principale, tandis que la principale reste intacte ;
- jeu positif ou nul réglable en millimètres ;
- plan d'appui associatif lié à un sommet de la barre principale, plan de jeu paramétrique, séparation du corps puis fonction Fusion `Retirer` pour la surlongueur ;
- traçabilité de la jonction et de la barre principale dans les attributs du composant secondaire ;
- guide complet d'installation depuis GitHub, incluant la méthode autonome et la place obligatoire du dossier `profiles`.

### Sécurisé

- refus des arcs, barres presque parallèles, chemins déconnectés, composants non générés par l'extension, corps multiples et seconde jonction sur la même barre secondaire ;
- suppression automatique des fonctions de jonction déjà créées si une étape ultérieure échoue ;
- première validation volontairement limitée à deux barres droites dont une extrémité secondaire rejoint l'axe de la principale.

### À valider dans Fusion

- premier essai sur deux IPE ou HEA perpendiculaires avec un jeu nul, puis avec `2 mm` ;
- conservation du corps principal et présence d'un seul corps visible dans le composant secondaire ;
- recalcul de la coupe après une modification raisonnable du squelette ou de la section principale ;
- annulation Fusion de la jonction et retour à la barre secondaire entière.

## [1.11.3] - En validation

### Corrigé

- aperçu jaune rafraîchi directement lors d'un changement de sélection, profil, ancrage, rotation ou miroir, même lorsque Fusion maintient la validation globale de la commande à l'état invalide ;
- aperçu désormais visible sur un chemin déjà occupé afin de comparer le nouveau profil avant de cocher volontairement son remplacement ;
- bouton `OK` toujours bloqué tant que le remplacement d'une barre existante n'est pas explicitement activé.

## [1.11.2] - En validation

### Corrigé

- adaptation automatique au repère du plan perpendiculaire créé par Fusion : si ses axes sont opposés ou tournés par rapport au squelette, l'esquisse finale est réalignée sur le repère exact de l'aperçu ;
- suppression du saut d'un coin d'ancrage au coin opposé observé dans certains documents, tout en conservant le comportement des dessins où les deux repères correspondaient déjà ;
- repère du chemin calculé par un module commun à l'aperçu et à la création finale pour les lignes et les arcs.

### Testé

- changement de base identité, inversion des deux axes et composition avec les miroirs couverts par des tests isolés ;
- refus d'un plan dont les axes ne formeraient pas un repère compatible avec le chemin.

## [1.11.1] - En validation

### Corrigé

- détection des lignes et arcs déjà utilisés par une barre créée avec l'extension, y compris les liaisons enregistrées par les anciennes versions ;
- prévention des corps superposés lorsqu'un chemin est déjà lié à une barre créée par l'extension ;
- validation désactivée lorsqu'un chemin est déjà occupé et que le remplacement n'est pas explicitement demandé.

### Ajouté

- case `Remplacer les barres déjà présentes`, désactivée par défaut ;
- rapport dynamique indiquant si les chemins sont libres ou listant les composants qui seront remplacés ;
- remplacement sécurisé : toutes les nouvelles barres sont créées et contrôlées avant le retrait des anciennes ; en cas d'échec de création, les anciennes restent intactes.

## [1.11.0] - En validation

### Ajouté

- nouvelle commande `Gérer les profils personnalisés V1.11.0` pour ajouter ou supprimer un profil personnel sans toucher aux 341 profils normalisés ;
- validation préalable des DXF personnalisés : fichier ASCII R12, taille limitée, géométrie 2D prise en charge, contours fermés, dimensions non nulles et confirmation explicite des millimètres ;
- catégorie `Personnalisés`, avec familles et désignations choisies par l'utilisateur, intégrée au même aperçu et au même processus de création que les profils européens ;
- stockage local hors du dépôt et hors du dossier du complément, avec chemins logiques relatifs enregistrés dans les barres ;
- suppression récupérable par déplacement du DXF et de ses métadonnées dans une corbeille locale horodatée ;
- avertissement avant suppression lorsqu'une ou plusieurs barres du document actif utilisent encore le profil.

### Sécurisé

- copie du DXF contrôlée par empreinte afin de conserver exactement le fichier source ;
- refus des doublons sans écrasement silencieux ;
- noms de dossiers et de fichiers neutralisés et résolus uniquement à l'intérieur de la bibliothèque personnelle ;
- refus de supprimer un profil appartenant à la bibliothèque normalisée.

### Limites de cette première phase

- seuls les DXF ASCII R12 dessinés en millimètres et compatibles avec le lecteur géométrique actuel sont acceptés ;
- la corbeille est récupérable sur disque, mais aucune commande de restauration n'est encore exposée dans Fusion ;
- l'aperçu visuel détaillé dans le gestionnaire sera ajouté dans une étape séparée ; l'aperçu jaune de création reste disponible après l'import.

## [1.10.0] - En validation

### Ajouté

- nouveau choix `Catégorie`, actuellement limité à `Zones géographiques` ;
- nouveau choix `Zone géographique`, actuellement limité à `Europe` ;
- enregistrement de la catégorie et de la zone dans chaque nouvelle barre, puis affichage dans l'inspecteur ;
- détection automatique de futures zones placées sous `profiles/Zones_geographiques`.

### Modifié

- déplacement sans altération des 341 DXF vers `profiles/Zones_geographiques/Europe/<famille>` ;
- compatibilité conservée avec les métadonnées et chemins relatifs des versions antérieures ;
- architecture préparée pour une future catégorie `Personnalisés`, distincte des zones géographiques.

## [1.9.7] - En validation

### Corrigé

- conservation de chaque matériau du document dans le menu même lorsque plusieurs copies Autodesk partagent le même identifiant interne ;
- résolution des matériaux du document par leur entrée de collection et leur nom exact, avec repli sûr lorsque l'ordre de la collection change ;
- sélection du S235JR par défaut désormais effective lorsque `Acier`, S235JR, S275JR et S355J2 partagent le même identifiant Fusion ;
- test reproduisant l'identifiant partagé observé dans Fusion et vérifiant l'affichage ainsi que la résolution exacte du S275JR.

## [1.9.6] - En validation

### Corrigé

- renommage explicite de chaque matériau après `Materials.addByCopy`, car Fusion pouvait conserver visuellement le nom du matériau modèle `Acier` ;
- relecture immédiate du nom réellement enregistré et annulation des copies créées si Fusion refuse le nom attendu ;
- test reproduisant une copie qui ignore son nom demandé et vérifiant les trois noms S235JR, S275JR et S355J2.

## [1.9.5] - En validation

### Ajouté

- création automatique et idempotente de `S275JR EN 10025-2 - t<=16 mm` dans le document actif ;
- propriétés physiques de première phase : `rho = 7 850 kg/m³`, `E = 210 GPa`, `nu = 0,30`, `ReH min = 275 MPa` et `Rm min = 410 MPa` ;
- présence du S275JR entre le S235JR et le S355J2 dans le menu des matériaux du document ;
- test dédié des valeurs de la nuance S275JR et adaptation des contrôles aux trois nuances.

### Inchangé

- le S235JR reste le matériau sélectionné par défaut.

## [1.9.4] - En validation

### Corrigé

- matériaux du document actif placés avant la longue liste des bibliothèques Autodesk ;
- `S235JR EN 10025-2 - t<=16 mm` sélectionné par défaut lorsqu'il existe dans le document ;
- S235JR et S355J2 immédiatement visibles à l'ouverture du menu, chacun avec la source `Document actif` ;
- test de priorité d'affichage et de sélection par défaut ajouté.

## [1.9.3] - En validation

### Corrigé

- traitement direct du coefficient de Poisson comme valeur sans dimension, même lorsque Fusion lui associe un identifiant d'unité interne non vide ;
- test reproduisant une propriété de Poisson déclarée `Unitless` par Fusion.

## [1.9.2] - En validation

### Corrigé

- prise en charge des noms internes d'unités renvoyés par Fusion, notamment `KilogramPerCubicMeter`, `Pascal`, `Megapascal` et leurs variantes usuelles ;
- conservation de la prise en charge des symboles métriques et impériaux déjà ajoutée en V1.9.1 ;
- tests reproduisant exactement l'unité de densité observée sur la machine Fusion de validation.

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
