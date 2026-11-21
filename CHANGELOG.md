# Historique des versions

Toutes les évolutions livrées de `fusion-free-structure` sont consignées ici.

## [Non publié]

## [1.30.18] - Fraisures et RIVKLE

- Ajoute un accès RIVKLE dans **Visserie**, avec la liaison au trou et des options séparées pour la vis et la rondelle sous tête.
- Prépare une fraisure à 90° concentrique à un trou rond pour un boulon ou une vis en trou taraudé.
- Dessine l’écrou dans les quatre icônes de boulons.

## [1.30.17] - Groupe Visserie

- Déplace **Boulonnerie JHR** dans le groupe natif **Visserie** du ruban Structure JHR.
- Ajoute les accès directs par type de tête et un accès pour les vis en trou taraudé. La longueur et les rondelles se règlent dans le formulaire de pose.
- Lie la fixation à une ouverture circulaire sur la face d’appui sous tête. Les oblongs restent disponibles en pose libre.

## [1.30.16] - Interface native du contreventement

- Retire la commande de palette. L’auto-contreventement se crée et se modifie dans les formulaires natifs de Fusion.
- La retouche des évidements reste ciblée sur la platine centrale. L’aperçu 3D masque temporairement le montage existant pendant sa modification.

## [1.30.15] - Détails et retouche de la platine centrale

- La palette présente le X complet, le détail de la platine centrale et celui d’un gousset d’about.
- Une modification limitée aux évidements remplace le contour de la platine dans son occurrence existante et garde les cornières, goussets et boulons.
- La palette distingue les accusés de réception du navigateur des commandes de modélisation.

## [1.30.14] - Aperçu et liaison de la palette

- Charge les fichiers de la palette à partir d’une adresse de fichier encodée pour Fusion.
- Allège les réponses envoyées à la palette et précise les erreurs de communication.
- Dans **Modifier un assemblage**, masque temporairement le montage existant pendant l’aperçu. Les cornières du X sont affichées avec leur section.

## [1.30.13] - Palette pilote du contreventement

- Le menu **Assemblages** permet d’ouvrir l’auto-contreventement dans une palette latérale avec schéma et aperçu dans la scène. Elle peut créer un X à partir de deux faces ou reprendre un X existant.

## [1.30.12] - Onglets de modification de l’auto-contreventement

- Prépare les onglets de réglages à l’ouverture de **Modifier un assemblage** et les affiche dès que la sélection désigne un X. Fusion peut ainsi valider les champs du formulaire.

## [1.30.11] - Reprise des cotes de l’auto-contreventement

- Réinjecte les cotes enregistrées comme valeurs numériques dans Fusion, y compris le déport latéral nul, et attribue des identifiants distincts aux groupes de réglages.

## [1.30.10] - Édition et platine du contreventement

- **Modifier un assemblage** reprend l’auto-contreventement depuis la sélection d’une de ses pièces.
- Les retraits haut et bas se mesurent sur chacune des faces sélectionnées.
- La platine centrale garde quatre grands chants d’équerre et quatre coupes couvrant l’aile. L’onglet **Options** propose des évidements arrondis à profondeur réglable.

## [1.30.9] - Auto-contreventement entre deux faces

- Création du X depuis les faces opposées des poteaux, avec sections, inversions, retraits, platine centrale à chants inclinés, goussets d’about et boulonnerie.
- Les sections conservent les arcs du DXF. Le X garde les deux faces de référence pour sa modification et son recalcul en fin d’historique.
- Les assemblages du catalogue peuvent être copiés indépendamment sur de nouveaux profils. La liaison des réglages est disponible pour les pieds de poteau modifiables.

## [1.30.8] - Méplats et copie des pieds de poteau

- Les goussets d’âme et d’ailes reçoivent deux méplats de débit réglables, de 10 mm par défaut.
- La commande Copier un assemblage reporte un pied sur un autre poteau, avec des réglages indépendants ou partagés.
- La taille de la platine se règle librement ou par les quatre débords du profil. Les perçages suivent les bords en X et/ou Y, ou conservent les entraxes saisis.
- Les cotes invalides affichent une alerte rouge dans le groupe concerné. Le contrôle des goussets tient compte du jeu réglable et de l’encombrement des rondelles.

## [1.30.7] - Hauteur hors tout des poteaux

- Les nouvelles platines de pied démarrent à la cote de l’extrémité de l’ébauche. Le profil est raccourci jusqu’à la face d’appui pour garder la longueur hors tout.
- La coupe est liée à l’épaisseur de la platine et revient à l’about d’origine à la suppression du pied.

## [1.30.6] - Pieds et gestion des assemblages

- Aperçu des tôles avec leurs faces, chants et ouvertures. Le formulaire du pied propose des choix de chanfrein et d’arrondi exclusifs.
- Ancrages droits avec rondelles et écrous. Goussets d’âme et d’ailes cumulables, avec largeur et chanfrein de dégagement réglables.
- Modification depuis la sélection d’une pièce et rotation liée des pieds lors de la modification du poteau.
- Suppression du groupe d’historique complet et de ses traces de jonction. Les grugeages automatiques des nouveaux raccords de pannes rejoignent le groupe.

## [1.30.5] - Raccordement des pannes en série

- Ajoute la commande Raccorder les pannes pour poser des plats d’âme aux abouts des pannes I/H sélectionnées, avec aperçu et réglages communs au lot.
- Repère les raccords existants et signale les abouts ambigus.

## [1.30.4] - Fonctions des profils

- Ajoute la fonction Barre, Poteau, Poutre ou Panne à la création et à la modification des profils acier.
- Le bouton Poteaux utilise une icône dédiée en H, distincte des pieds de poteau.

## [1.30.3] - Accès directs et profils éditables

- Corrige l’ouverture du formulaire d’assemblage en utilisant des libellés de sélection fixes.
- Accès directs aux pieds de poteau, raccords poutre-poteau, raccords poutre-poutre et contreventements.
- Commande Poteaux depuis des points et commande Modifier un profil avec ses réglages de création.

## [1.30.2] - Dialogue des assemblages

- Accès direct aux pieds de poteau, avec quatre onglets et des cases pour les accessoires facultatifs.
- Aperçu sur les profils sélectionnés avec contour des perçages et message en cas d’échec.

## [1.30.1] - Appuis de goussets et coupes de barreaux

- Gousset soudé pour une cornière avec flanc incliné, retour d’équerre et couverture de toute l’aile dans la zone boulonnée.
- Appui des goussets au choix sur l’aile ou sur l’âme, avec centrage ou déport réglable selon le plan de la cornière.
- Jeu réglable entre l’about de la cornière et la face soudée. L’ajustage se fait avant les perçages et contrôle la position de l’autre bout.
- Les barreaux se terminent sur une coupe plane tangente sous la main courante ronde.

## [1.30.0] - Cornières opposées, arborescence et garde-corps

- Deux secondaires face à face partagent une grille de boulons traversants dans l’âme principale. La proposition de cornières mesure la hauteur d’âme réellement libre après grugeage.
- Les assemblages regroupent leurs pièces nommées et leur visserie par tête, diamètre et longueur. Les créations sont repliées dans l’historique par commande.
- Le tronçonnage au droit d’un poteau plat crée deux demi-poteaux ou un plat adjacent. En rampant, seule la main courante est coupée d’équerre à son axe. La sous-lisse et la plinthe suivent la jonction des plats.
- Le modèle barreaudé, en pose à la française ou à l’anglaise, propose des barreaux carrés, ronds ou plats et contrôle le vide au repos en géométrie, avec un plafond de 100 mm.

## [1.29.4] - Repère des garde-corps et inserts sertis

- Le garde-corps accepte Y ou Z comme verticale. En automatique, la préférence Fusion est utilisée si les appuis et le parcours concordent.
- Le bourrelet RIVKLE ressort derrière la paroi et le corps se termine par un chanfrein extérieur. Le modèle après pose conserve l'enveloppe du catalogue.
- Le guide Fusion et MCP est référencé depuis les consignes du dépôt.

## [1.29.3] - Goussets de contreventement et garde-corps industriels

- Les goussets sur porteur ont une assise évasée et suivent les cornières. La longueur d'appui est réglable sur les modèles à une, deux et trois diagonales.
- Les garde-corps ont une plinthe 150 × 6 par défaut, avec choix du côté et un jeu réglable de 10 mm au-dessus du parcours. Les poteaux plats reçoivent une tête à deux biais avec méplat sous la main courante, en palier et en rampant.

## [1.29.2] - Changement de section avec assemblage lié

- La commande de remplacement modifie le balayage existant d’une barre liée. Elle conserve le chemin, le composant et les références si les assemblages correspondent à la nouvelle section.
- Vérifié dans Fusion sur un pied lié. Passage IPE 160 vers IPE 200, puis retour automatique à l’IPE 200 après refus de l’IPE 450 incompatible avec la platine.

## [1.29.1] - Éclissages liés et inspection des assemblages

- Les nouveaux éclissages suivent un déplacement commun des deux profils avec le même jeu. Les perçages sont projetés depuis les tôles et les boulons suivent leur groupe. Les couvre-joints sur ailes inclinées UPN conservent leur pose calculée à la création.
- La commande Inspecter un assemblage accepte le groupe ou l’une de ses tôles et signale les écarts avec la géométrie attendue.

## [1.29.0] - Contreventements, raccords en pente et garde-corps

- Recoupe de deux cornières en X en quatre branches, avec un gousset de niveau. Goussets soudés sur porteur I/H pour une à trois cornières.
- About d’arbalétrier sur poteau et suivi des abouts droits avec ou sans jarret après un déplacement du nœud.
- Ancrages droits, préscellement et assises biaises pour l’éclissage d’ailes UPN.
- Vis et rondelle associées aux RIVKLE. Garde-corps acier sur dessus ou sur âme, raccord palier-rampant, perçage optionnel du support acier et représentation d’ancrages sur béton.

## [1.28.3] - Plats d’âme et perçages liés au squelette

- Pour un nouveau plat d’âme, les perçages de la poutre secondaire sont projetés depuis le plat. Le raccord et sa boulonnerie suivent l’extrémité de la poutre.
- L’inspection contrôle les perçages traversants et la pose des boulons. Les changements de position et de longueur ont été essayés dans Fusion, avec le plat sur les deux faces de l’âme.

## [1.28.2] - Têtes cylindriques et bombées six pans creux

- Pose CHC de M4 à M24 et TBHC de M4 à M16 dans Boulonnerie JHR et via le MCP, avec empreinte creuse et longueur calculée depuis les appuis.
- Contrôle Fusion des deux formes de tête, dont une pose M6 sur perçage rond et une pose M6 sur oblong.

## [1.28.1] - Pieds liés au squelette

- À la création, une liaison rigide Fusion rattache le pied à l’extrémité choisie. La platine, ses perçages, les cales et les goussets suivent le déplacement du profil.
- L’inspection compare la position réelle des tôles à la position calculée. La commande interdit un deuxième pied au même bout, même après déplacement du poteau.

## [1.28.0] - Assemblages boulonnés et portique d’essai

- Pieds chanfreinés ou déportés, cales fourchettes, chanfreins et arrondis de platines.
- Boulonnage automatique des abouts, faîtages, plats d’âme et doubles cornières avec contrôle d’interférence.
- Éclissage d’âme d’un côté, des deux côtés ou avec couvre-joints d’ailes. Jarrets de faîtage et gousset central de quatre cornières.
- Écrous RIVKLE à trois formes de tête avec référence de catalogue et option de préparation de l’avant-trou.
- Diagnostic MCP des profils sources modifiés depuis la pose. Nouveaux pictogrammes isométriques.

## [1.27.0] - Coupes stables et assemblages à platines

- Plan d’onglet piloté par les deux lignes d’esquisse, avec remplacement des faces d’about.
- Jonction droite avec jeu conservé au recalcul et pose des cornières capturée avant perçage.
- Catalogue à platines partagé par le ruban et le mode script du MCP Autodesk Fusion.
- Boulons H sur trou rond ou oblong, tête fraisée avec empreinte six pans et bord droit, vis H en taraudage ISO.

## [1.26.0] - Regroupement automatique de la timeline

- chaque nouvelle barre est regroupée et repliée dans la timeline sous le nom de son composant ;
- les jonctions, onglets et grugeages sont regroupés après leur réussite, dans le groupe de la barre si les opérations sont adjacentes, sinon dans des groupes distincts nommés d'après la barre ; aucun déplacement de fonction paramétrique ;
- dégroupage sans suppression de fonctions avant le retrait d'une barre lors d'un remplacement ou d'une annulation ;
- toutes les corrections de grugeage de la V1.25.3 sont conservées ; bibliothèque DXF inchangée ;
- un prolongement isolé non adjacent reste individuel : Fusion exige au moins deux fonctions par groupe.

## [1.25.3] - Plans de grugeage rattachés aux faces principales

### Corrigé

- l'analyse visuelle dans Fusion a isolé le premier défaut : après modification de longueur, `PLAN_ORIENTATION_AME_PRINCIPALE` reste en place mais sa direction interne peut s'inverser ; ses deux décalages signés envoient alors `PLAN_DEBUT_GRUGEAGE` et `PLAN_COUPE_AME_PRINCIPALE` du mauvais côté ;
- ces deux plans ne dépendent plus du sens de cette normale. Ils référencent directement les faces longitudinales correspondantes de la barre principale : face extérieure et face d'âme ;
- `PLAN_REFERENCE_ESQUISSE_GRUGEAGE`, qui restait correctement placé, n'est pas modifié.

### Garde-fous sur les corps

- l'extrusion de grugeage conserve son corps secondaire participant explicitement désigné ;
- la séparation doit produire exactement deux corps ; le corps intérieur est choisi par sa position géométrique, un seul excédent est retiré, puis Fusion doit retrouver exactement un corps du bon côté ;
- la coupe directe défectueuse de la V1.25.1 n'est pas réintroduite.

### Périmètre du test

- recréer un seul grugeage I/H neuf à `90°`, afficher les trois plans, modifier uniquement une longueur et contrôler leurs positions avant d'examiner les fonctions de coupe ;
- les anciens grugeages ne sont pas migrés automatiquement.

## [1.25.2] - Rétablissement du grugeage stable

### Corrigé

- la coupe directe expérimentale de la V1.25.1 est retirée : selon l'orientation du composant, elle pouvait supprimer le mauvais volume et détruire la forme de la barre secondaire ;
- la séparation contrôlée puis la suppression de l'excédent sont restaurées, ainsi que la limitation explicite de la coupe aux corps participants ;
- la création géométrique correcte du grugeage redevient prioritaire. La mise à jour dynamique après modification du squelette reste ouverte et ne doit pas être considérée comme corrigée.

### Important

- un grugeage créé avec la V1.25.1 conserve sa mauvaise opération dans l'historique Fusion et doit être supprimé puis recréé avec la V1.25.2 ;
- ce correctif ne modifie automatiquement aucun document Fusion existant.

## [1.25.1] - Coupe directe du grugeage

### Corrigé

- la chaîne fragile `Split Body` puis `Remove Body` est supprimée du grugeage ;
- une extrusion de coupe enlève désormais directement le demi-espace extérieur au plan de l'âme principale ;
- aucun petit corps intermédiaire ne doit donc perdre sa référence lorsque le balayage du profil se recalcule ;
- la coupe principale du grugeage ne mémorise plus explicitement un corps participant : le composant de barre, qui contient un corps unique, fournit automatiquement le corps intersecté.

### Diagnostic confirmé

- le test Fusion V1.25.0 a confirmé l'échec de `COUPE_DROITE_AME_PRINCIPALE`, puis la perte du corps temporaire dans `RETRAIT_APRES_AME_PRINCIPALE` ;
- un grugeage V1.25.1 neuf ne doit plus créer la fonction `RETRAIT_APRES_AME_PRINCIPALE` dans l'historique.

### Résultat Fusion

- solution retirée en V1.25.2 : l'essai réel a montré que le mauvais demi-espace pouvait être supprimé selon l'orientation du profil.

## [1.25.0] - Première liaison dynamique du grugeage

### Corrigé

- les plans de station du grugeage ne mémorisent plus la proportion calculée sur la ligne principale au moment de la création ;
- les deux plans prennent maintenant leur position sur le point d'extrémité réel de la ligne secondaire et leur orientation sur les plans médians paramétriques des deux barres ;
- une modification de longueur du squelette peut ainsi déplacer la rencontre sans laisser les fonctions `COUPE_DROITE_AME_PRINCIPALE`, `RETRAIT_APRES_AME_PRINCIPALE` et `GRUGEAGE_PROFIL_OUVERT` à leur ancienne station ;
- chaque nouveau grugeage enregistre le mode de référence dynamique utilisé afin de distinguer les anciennes opérations.

### Périmètre de validation

- cette première étape vise un unique grugeage IPE/HEA/HEB neuf ; les opérations créées avec une version antérieure doivent être supprimées puis recréées ;
- le test porte d'abord sur une variation de longueur à direction constante. Le changement d'angle et la mise à jour des anciens grugeages restent séparés.

## [1.24.5] - Centrage indépendant de l'ancrage

### Corrigé

- `Décalage vertical = 0 mm` centre maintenant les doubles cornières et leur motif de perçage sur la hauteur libre réelle de l'âme secondaire ;
- le point d'ancrage DXF choisi pour générer la barre ne sert plus, à tort, de centre vertical à l'assemblage ;
- la prévisualisation, les contrôles de sortie d'âme et la création finale partagent le même décalage géométrique ;
- un essai automatique couvre désormais le cas d'un profil ancré en haut, qui reproduisait le refus observé dans Fusion.

### Inchangé

- le décalage saisi par l'utilisateur reste appliqué dans l'axe vertical du profil, mais il est désormais mesuré depuis le centre de l'âme libre ;
- le chemin sûr V1.24.4 pour ouvrir la fenêtre native d'attaches reste inchangé et aucune commande texte automatique n'est réintroduite.

## [1.24.4] - Test manuel sécurisé

### Corrigé

- la sonde automatique et son second événement personnalisé sont entièrement retirés ; l'ouverture native revient au chemin déjà validé de la V1.24.2 ;
- le diagnostic éventuel doit maintenant être lancé manuellement, une seule fois, uniquement après avoir traité la demande `Capturer la position` et attendu le chargement complet du catalogue ;
- `UI.CurrentCommandInfo`, identifié dans la pile du crash, n'est plus utilisé pour cette fenêtre.

### Sécurité du test

- le complément n'exécute plus aucune commande texte pendant que `FusionFastenersCommand` est actif ;
- le prochain essai se fait dans un document jetable et commence par la seule commande de lecture `Toolkit.cmdDialog` saisie manuellement dans la palette Fusion.

## [1.24.3] - Échec confirmé dans Fusion le 2026-08-21

### Incident

- une première sonde automatique devait lire `UI.CurrentCommandInfo`, puis `Toolkit.cmdDialog`, après l'ouverture des attaches ;
- Fusion s'est fermé pendant la première lecture, avant toute écriture de résultat ; le fichier local ne contient que son en-tête ;
- le CER horodaté `08:36:18` place `Application::executeTextCommand_raw`, `InteractiveCommandBase::commandInputSet` et `Application::fireCustomEvent` sur le thread du crash, pendant le chargement asynchrone de la bibliothèque d'attaches.

### Conclusion

- une temporisation fixe n'est pas un critère de disponibilité fiable pour cette fenêtre web native ;
- la V1.24.3 ne doit plus être utilisée et est remplacée par la V1.24.4.

## [1.24.2] - En validation

### Corrigé

- le déclenchement de l'événement natif ne part plus directement de l'événement `destroy` de la commande JHR, chemin refusé par Fusion avec le message « n'a pas pu planifier » ;
- un thread de coordination attend `0,1 s`, puis appelle uniquement `fireCustomEvent` jusqu'à trois fois ; Fusion traite ensuite l'ouverture native sur son thread principal lorsqu'il est au repos ;
- la création des cornières, les quatre groupes de perçages et la sélection des six arêtes restent strictement inchangés.

### Validation prévue

- vérifier que `Insérer une attache` s'ouvre après fermeture du message JHR, puis contrôler si les six arêtes de deux orientations sont conservées ensemble.

## [1.24.1] - Échec d'ouverture confirmé dans Fusion

### Modifié

- les boulons reconstruits par cinq corps sont retirés avant leur validation Fusion au profit de la commande native `Insérer une attache` ;
- après création des cornières et des quatre groupes de trous, le complément retrouve six arêtes circulaires réelles : quatre sur la face arrière de l'âme principale et deux sur la face extérieure de la cornière gauche ;
- à la destruction de la commande JHR, un événement personnalisé devait reporter la présélection des six arêtes et l'ouverture de `FusionFastenersCommand` jusqu'au retour au repos de Fusion ; l'appel direct à `fireCustomEvent` depuis cet événement a été refusé par Fusion avant la mise en file ;
- l'aperçu bleu matérialise uniquement la tête et la tige visées, tandis que la norme, la longueur, le matériau, la finition, les écrous et les rondelles sont laissés à la bibliothèque native Fusion.

### Sécurité

- aucune API expérimentale de bibliothèque d'attaches n'est utilisée ; le complément s'appuie seulement sur la sélection active et l'exécution de la commande native publique ;
- si la fenêtre native ne peut pas être ouverte, les cornières et trous validés restent créés et un message indique le chemin manuel `Solide > Insérer > Insérer une attache` ;
- l'annulation de la commande JHR avant `OK` n'ouvre jamais la fenêtre native.

### Limite à valider

- Fusion doit confirmer pendant le test réel qu'une seule ouverture accepte simultanément les quatre axes principaux et les deux axes secondaires ; les choix du catalogue natif ne peuvent pas être préremplis par l'API publique actuelle.

## [1.24.0] - Remplacé par la V1.24.1 avant validation Fusion

### Ajouté

- choix dynamique de boulons métriques `M12`, `M16`, `M20` ou `M24`, classe affichée `8.8`, avec adaptation automatique du diamètre de perçage conseillé ;
- aperçu bleu des tiges, têtes, écrous et deux rondelles, calculé depuis les mêmes centres et axes que les trous rouges ;
- création d'un composant indépendant par boulon, avec corps nommés pour la tige, la tête hexagonale, les deux rondelles et l'écrou hexagonal ;
- pour deux rangées, quatre boulons relient séparément chaque cornière à l'âme principale et deux boulons traversent ensemble les deux cornières et l'âme secondaire ;
- longueur calculée depuis les épaisseurs réelles des deux âmes et de la cornière, les rondelles, l'écrou et une sortie de filetage, puis arrondie par excès au pas de `5 mm` ;
- attributs de traçabilité sur chaque composant de boulon : diamètre, classe, groupe de liaison, côté, rangée, serrage, longueur et version du complément.

### Sécurité

- un diamètre de trou inférieur ou égal au diamètre nominal du boulon est refusé avant toute création ;
- une incohérence entre les deux centres secondaires et l'épaisseur réelle de l'âme annule la commande ;
- si la création d'un boulon échoue, tous les trous, cornières et boulons de la tentative sont retirés.

### Limites explicites

- le filetage n'est pas modélisé et la classe `8.8` reste une désignation de fixation, pas un calcul de résistance ;
- le matériau physique des corps de boulon est provisoirement repris sur la barre secondaire, sans prétendre représenter un matériau certifié de boulonnerie.

## [1.23.6] - Validé dans Fusion le 2026-08-20

### Corrigé

- les trous des âmes principale et secondaire utilisent désormais la même coupe circulaire symétrique que les cornières, limitée explicitement au corps de la barre concernée ;
- sur une esquisse portée par une face, seuls les profils constitués d'une boucle unique et d'une courbe circulaire sont transmis à la coupe ; la région de fond et ses boucles intérieures sont exclues ;
- correction de l'échec V1.23.5 du groupe `PERCAGES_ASSEMBLAGE_CORNIERES_SECONDAIRE` avec `ZERO_DISTANCE_ERROR`, `HOLE_CANNOT_CREATE_TOOLBODY` et `InternalValidationError`.

## [1.23.5] - En validation

### Corrigé

- les cercles de coupe des cornières sont maintenant dessinés sur les plans locaux d'origine `XZ` et `YZ`, perpendiculaires aux axes de perçage concernés ;
- aucune face du solide n'est utilisée comme support de ces deux esquisses : Fusion ne peut donc plus ajouter la région de fond de la face aux deux disques de coupe ;
- correction de l'annulation V1.23.4 `3 régions circulaires obtenues au lieu de 2` pour le groupe `PERCAGES_VERS_AME_PRINCIPALE`.

### Bloqué pendant la validation

- les coupes des deux cornières passent, mais la fonction native de perçage reste refusée sur l'âme secondaire ; la commande est annulée avant le contrôle final du placement.

## [1.23.4] - En validation

### Corrigé

- les trous propres aux deux branches des cornières sont maintenant produits par des coupes cylindriques symétriques traversantes, centrées sur les mêmes coordonnées et avec le même diamètre que l'aperçu rouge ;
- la coupe traverse volontairement les deux côtés du plan porteur et limite explicitement le corps participant, ce qui évite les erreurs Fusion `ZERO_DISTANCE_ERROR`, `NO_TARGET_BODY` et `HOLE_CANNOT_CREATE_TOOLBODY` rencontrées avec la fonction native de perçage sur une face locale ;
- les perçages des âmes principale et secondaire conservent la fonction native de perçage, et leur éventuel message d'échec indique maintenant le groupe concerné.

### Bloqué pendant la validation

- une esquisse créée directement sur la face extérieure exposait également la région de fond de cette face ; Fusion retournait donc trois profils pour deux cercles et la création était annulée avant la coupe.

## [1.23.3] - En validation

### Corrigé

- chaque cornière est maintenant importée, extrudée et percée dans un composant encore placé à l'identité ; son placement final n'est appliqué qu'après la création de toutes ses fonctions locales ;
- les centres rouges validés dans l'aperçu sont convertis mathématiquement dans le repère rigide de chaque cornière avant les perçages locaux ;
- l'enveloppe réelle de chaque occurrence est comparée à l'enveloppe attendue après placement ; une divergence annule toute la tentative au lieu de conserver un assemblage décalé.

### Bloqué pendant la validation

- Fusion refusait les perçages locaux des cornières avant leur placement avec une distance nulle dans un sens et aucun corps cible dans l'autre ; la validation du nouveau placement n'a donc pas encore pu être atteinte dans cette version.

### Diagnostic

- la V1.23.2 supprimait le contexte de création redondant, mais conservait l'import DXF dans une occurrence déjà orientée ; ce chemin Fusion produisait encore un résultat différent du repère direct utilisé par l'aperçu.

## [1.23.2] - En validation

### Corrigé

- la transformation d'occurrence n'est plus réappliquée aux extrusions et perçages créés nativement dans chaque composant de cornière ; cette correction seule n'a pas supprimé le décalage constaté dans Fusion ;
- les deux corps de cornière et leurs trous utilisent maintenant un seul repère : leurs fonctions restent locales et l'occurrence porte seule leur position dans l'assemblage ;
- les centres mondiaux des trous dans les âmes et le calcul validé de l'aperçu restent inchangés.

## [1.23.1] - En validation

### Corrigé

- après l'import DXF dans un composant déjà orienté, la position réellement obtenue est maintenant mesurée puis translatée pour ramener exactement le coin bas-gauche sur l'ancrage local `BL` ;
- le contrôle strict des dimensions et de l'ancrage reste exécuté après ce recalage : aucune extrusion n'est créée si la section ne correspond toujours pas au DXF ;
- correction de l'échec Fusion `Le DXF Cornière égale 50 × 50 — ép. 5 mm n'est pas positionné sur l'ancrage BL` rencontré avec la V1.23.0.

## [1.23.0] - En validation

### Ajouté

- création réelle de deux composants de cornière indépendants depuis le DXF sélectionné, avec matériau physique repris sur la barre secondaire ;
- perçages traversants alignés dans les deux branches de chaque cornière, dans l'âme principale et dans l'âme secondaire ;
- réglages dynamiques du diamètre, du nombre de rangées, de l'entraxe vertical et des distances de perçage sur les deux branches ;
- cercles rouges dans l'aperçu, calculés à partir des mêmes centres et du même diamètre que les trous finaux ;
- noms prévisibles `ASSEMBLAGE_CORNIERES_###_GAUCHE/DROITE` et attributs relatifs décrivant la section et le motif de perçage.

### Sécurisé

- refus avant création lorsque le trou sort d'une branche, de la hauteur de cornière ou de la hauteur libre d'une âme ;
- les valeurs proposées (`Ø18`, deux rangées, entraxe `50 mm`, distances `30 mm`) sont identifiées comme valeurs de dessin modifiables et non comme un dimensionnement de résistance ;
- si Fusion refuse une extrusion ou un perçage, les trous déjà ajoutés aux barres et les deux nouveaux composants sont supprimés dans l'ordre inverse ;
- aucun boulon n'est créé dans cette étape ; les angles obliques, chemins cintrés et profils hors IPE/HEA/HEB restent refusés ;
- 145 tests automatiques couvrent le repère direct des deux composants, le motif centré, l'alignement des trous, les limites de matière, l'aperçu rouge et les régressions existantes.

## [1.22.0] - Validée dans Fusion

### Ajouté

- nouveau groupe `ASSEMBLAGES` dans l'onglet `STRUCTURE JHR` et commande `Assemblage par cornières — aperçu` ;
- première phase volontairement limitée à deux profils IPE/HEA/HEB droits dont les axes se rejoignent à `90°` ;
- choix d'une cornière égale européenne dans la bibliothèque DXF, avec `50 × 50 — ép. 5 mm` proposé par défaut ;
- réglages dynamiques de la hauteur des cornières et de leur décalage vertical ;
- aperçu jaune de deux cornières symétriques, chacune posée sur une face de l'âme secondaire et contre la face de l'âme principale orientée vers elle ;
- réutilisation des mêmes axes, ancrages et transformations de profils que les jonctions et le grugeage.

### Limité pour validation

- `OK` ferme uniquement la phase d'aperçu : aucun composant, corps, trou, boulon ou historique n'est créé ;
- les angles obliques, les chemins cintrés, les profils hors IPE/HEA/HEB, les cornières inégales et le dimensionnement de résistance restent refusés ou hors périmètre ;
- 140 tests automatiques couvrent le contour DXF, les deux placements symétriques, les refus du premier périmètre, le branchement de la commande et les régressions existantes.

## [1.21.0] - En validation

### Ajouté

- nouveau groupe `PARAMÈTRES` dans l'onglet `STRUCTURE JHR` et bouton `Paramètres Structure JHR` ;
- première fenêtre de configuration avec l'onglet `Valeurs par défaut`, organisé par type d'opération et groupe de profils ;
- jeux de jonction ajustée indépendants pour IPE/HEA/HEB, cornières/tés, tubes et autres profils ;
- valeurs séparées pour le grugeage I/H et le grugeage cornières/tés ; la coupe d'onglet indique qu'elle ne possède encore aucune valeur réglable ;
- sauvegarde locale dans `%APPDATA%\EI_JHR\fusion-free-structure\settings.json`, hors du dépôt, de la bibliothèque DXF et des documents Fusion ;
- application automatique du jeu correspondant à la famille de la barre secondaire lors de sa sélection, tout en conservant la possibilité de modifier ponctuellement la valeur dans la commande.

### Sécurisé

- le fichier contient uniquement un numéro de schéma et des distances numériques positives ou nulles ;
- l'écriture est atomique et un fichier illisible n'est jamais remplacé sans validation explicite par `OK` dans la fenêtre Paramètres ;
- l'absence de fichier conserve toutes les valeurs historiques : `0 mm` pour les jonctions ajustées et `1 mm` pour les jeux de grugeage ;
- 134 tests automatiques couvrent le stockage, la validation, le regroupement des familles et le branchement des commandes.

## [1.20.2] - En validation

### Ajouté

- réglage `Jeu sous l'âme secondaire` pour les cornières et les tés : le retrait droit vaut désormais l'épaisseur réelle de la branche secondaire plus ce jeu explicite ;
- réglage indépendant `Jeu autour du congé principal`, qui agit uniquement sur le rayon du dégagement arrondi ;
- affichage conditionnel des réglages : les deux nouveaux jeux apparaissent seulement pour un couple cornière/té, tandis que `Jeu vertical I/H` reste seul pour un couple IPE/HEA/HEB ;
- enregistrement séparé des deux nouvelles valeurs dans les données de l'opération.

### Régression couverte

- un jeu sous âme nul conserve exactement l'épaisseur de branche validée en V1.20.1 ;
- le déplacement du retrait droit et de son arête arrondie suit la même valeur de jeu sous âme ;
- le rayon du congé reste indépendant et le double grugeage I/H n'utilise aucun des deux nouveaux réglages ;
- 128 tests automatiques passent avant l'essai Fusion.

## [1.20.1] - En validation

### Corrigé

- pour les cornières et les tés uniquement, le retrait droit de la secondaire s'arrête maintenant à l'épaisseur exacte de sa branche horizontale, sans englober son congé intérieur ;
- un dégagement arrondi séparé retire la matière nécessaire pour échapper le congé intérieur de la cornière ou du té principal ; son rayon correspond au rayon détecté dans le DXF principal augmenté du jeu demandé ;
- le côté réellement tourné vers la secondaire est pris en compte : aucune découpe arrondie n'est ajoutée contre la face extérieure d'une cornière dépourvue de congé intérieur ;
- la preview rouge distingue le retrait droit et le dégagement arrondi, puis la création Fusion ajoute la fonction `DEGAGEMENT_CONGE_PRINCIPAL` après `GRUGEAGE_PROFIL_OUVERT`.

### Régression couverte

- les 46 cornières et 11 tés fournis conservent une épaisseur et un rayon intérieur détectables ;
- le double grugeage des IPE, HEA et HEB ne passe pas par cette nouvelle logique et conserve ses limites, ses jeux et ses deux volumes existants ;
- 127 tests automatiques valident la géométrie, les profils fournis et le câblage du complément avant le premier essai Fusion.

## [1.20.0] - En validation

### Ajouté

- commande renommée `Grugeage profils ouverts` et prise en charge des quatre combinaisons `cornière → cornière`, `cornière → té`, `té → cornière` et `té → té` ;
- détection automatique des deux faces de la branche verticale et de la naissance du congé directement dans les 46 DXF de cornières et les 11 DXF de tés ;
- retrait simple de la branche horizontale de la secondaire, avec le même angle réel, les mêmes plans obliques, la même preview rouge et les mêmes prolongements que le double grugeage I/H ;
- face de coupe choisie sur la branche verticale de la principale selon son orientation réelle et le côté depuis lequel arrive la secondaire ;
- enregistrement du type général `open_profile_cope` et des familles principale/secondaire, tout en reconnaissant les anciens types `double_ipe_cope` et `double_ih_cope`.

### Sécurisé

- les 57 profils cornières/tés fournis possèdent tous une branche verticale et une zone de grugeage détectables ;
- l'esquisse finale exige maintenant autant de régions fermées que de volumes calculés : deux pour I/H, une pour cornière/té ;
- les mélanges I/H ↔ cornière/té, les chemins cintrés et les familles non analysées restent refusés sans modification ;
- les quatre combinaisons L/T doivent être validées séparément dans Fusion avant toute extension supplémentaire.

## [1.19.1] - En validation

### Corrigé

- correction du grugeage oblique dont la coupe d'âme suivait le bon angle mais dont le début du retrait des semelles restait perpendiculaire à la secondaire ;
- création de `PLAN_DEBUT_GRUGEAGE` parallèle au plan de l'âme et placé sur la face extérieure de la principale, avec le jeu longitudinal mesuré suivant l'axe secondaire ;
- conservation d'un plan séparé `PLAN_REFERENCE_ESQUISSE_GRUGEAGE`, normal à la secondaire et placé derrière toute la limite oblique, uniquement pour porter les deux profils fermés ;
- retrait supplémentaire de `0,5 mm` du plan de référence afin qu'il ne soit jamais tangent au plan de départ oblique ;
- extrusion en retrait limitée au départ par `FromEntityStartDefinition` sur le plan extérieur oblique et à l'arrivée par `ToEntityExtentDefinition` sur le plan d'âme oblique ;
- preview rouge reconstruite entre ces deux plans parallèles : ses faces de départ et d'arrivée suivent maintenant le même angle réel.

### Régression couverte

- aux angles `30°`, `45°` et `60°`, les quatre sommets de départ appartiennent au plan extérieur et les quatre sommets d'arrivée au plan de l'âme ;
- le comportement à `90°` reste le cas particulier où ces deux plans sont également normaux à la secondaire.

## [1.19.0] - En validation

### Ajouté

- commande renommée `Grugeage I/H` et secondaires étendues aux 18 IPE, 15 HEA et 15 HEB de la bibliothèque européenne ;
- suppression de l'hypothèse d'un angle droit : tout angle non parallèle supérieur à la limite géométrique de `5°` peut être évalué ;
- profondeur automatique calculée sur toute la largeur du profil secondaire, et non plus uniquement sur son axe, afin que le début du grugeage reste derrière toute la face extérieure de la principale ;
- volumes rouges transformés en outils obliques dont chaque sommet se termine exactement sur le plan de l'âme principale ;
- création paramétrique du plan d'âme incliné à partir des deux plans de station, de leur axe d'intersection et d'un plan orienté avant application du jeu ;
- coupe droite, prolongements et double grugeage final utilisant tous le même point et la même normale que la preview.

### Compatibilité

- les anciens enregistrements `double_ipe_cope` de la V1.18.0 restent reconnus pour empêcher un doublon sur la même extrémité ;
- les nouveaux traitements utilisent le type général `double_ih_cope` sans modifier les fonctions déjà présentes dans les documents.

### Sécurisé

- les 48 profils I/H fournis possèdent tous une âme et deux zones de semelles détectables ;
- un plan presque parallèle à la secondaire, un début de grugeage placé après le plan d'âme ou une coupe ne retirant aucune matière sont refusés avec annulation complète ;
- la V1.19.0 doit d'abord être validée dans Fusion sur un seul raccord HEA à `60°` avant les essais supplémentaires.

## [1.18.0] - En validation

### Ajouté

- activation du bouton `OK` de la commande `Grugeage IPE` pour créer réellement le premier double grugeage à `90°` ;
- création de trois références paramétriques dans la secondaire : plan d'extrémité, plan de coupe contre l'âme principale et plan de début du grugeage ;
- prolongement automatique de la principale lorsqu'elle ne couvre pas la section de la secondaire, avec la même fonction déjà éprouvée pour les jonctions droites ;
- prolongement éventuel de la secondaire jusqu'au plan de l'âme, séparation à ce plan et retrait de son excédent ;
- esquisse de deux outils fermés sur le plan de début du grugeage, puis coupe des semelles exactement jusqu'au plan de l'âme principale ;
- enregistrement du grugeage et de l'extrémité utilisée sans bloquer l'extrémité opposée de la même barre.

### Sécurisé

- la prévisualisation et les fonctions finales partagent exactement les mêmes points, directions, profondeurs et jeux ;
- la création est annulée si la coupe ne retire aucune matière mesurable ou si la secondaire ne conserve pas un corps unique ;
- en cas d'échec, les attributs, coupes, esquisses, plans et prolongements créés pendant la tentative sont supprimés dans l'ordre inverse ;
- le périmètre reste volontairement limité à une principale IPE, HEA ou HEB, une secondaire IPE droite et des axes à `90°` jusqu'à validation dans Fusion.

### Validé dans Fusion

- création réelle confirmée avec une principale suffisamment longue, sans prolongement inutile ;
- prolongement de la bonne extrémité confirmé lorsque la principale est trop courte ;
- deux grugeages successifs confirmés aux extrémités opposées d'une même barre secondaire.

## [1.17.1] - En validation

### Corrigé

- ajout d'une coupe droite de la secondaire référencée sur la face de l'âme principale orientée vers elle, au lieu de laisser son âme atteindre l'axe principal ;
- nouveau `Jeu contre l'âme`, indépendant des jeux vertical et longitudinal du grugeage ;
- réutilisation du calcul de couverture de la jonction droite pour détecter une principale trop courte à proximité du raccord ;
- indication de chaque longueur de prolongement nécessaire dans le rapport ;
- aperçu orange du plan de coupe contre l'âme et aperçu vert de la portion à ajouter à la principale ;
- prise en charge de la détection d'âme sur les 18 IPE, 15 HEA et 15 HEB, qu'ils soient décrits par polyligne ou par lignes et arcs.

### Sécurité de validation

- les ajouts verts, la coupe orange et les retraits rouges restent exclusivement graphiques ;
- aucune barre n'est encore prolongée ou coupée par cette commande et le bouton `OK` reste masqué.

## [1.17.0] - En validation

### Ajouté

- nouvelle commande `Grugeage IPE — aperçu` dans `STRUCTURE JHR > MODIFIER` ;
- premier périmètre volontairement limité à une principale IPE, HEA ou HEB, une secondaire IPE droite et des axes à `90°` ;
- détection automatique des limites des semelles et de l'âme directement dans chacun des 18 DXF IPE d'origine ;
- deux volumes rouges semi-transparents représentant la matière proposée au retrait au-dessus et au-dessous de l'âme ;
- profondeur calculée depuis l'axe commun jusqu'à la face réelle de la principale, sans dépendre de sa longueur totale ;
- prise en compte de l'ancrage, de la rotation et des miroirs enregistrés sur l'IPE secondaire ;
- jeux vertical et longitudinal réglables avec rafraîchissement dynamique du rapport et de l'aperçu.

### Sécurité de validation

- cette première livraison ne crée aucune fonction, aucune coupe et aucune entrée d'historique Fusion ;
- le bouton `OK` est volontairement masqué : la fenêtre se ferme uniquement avec `Fermer` ;
- la coupe réelle restera bloquée jusqu'à la validation visuelle du test 22 dans Fusion.

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
