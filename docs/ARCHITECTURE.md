# Architecture de la V1

## Interface Fusion dédiée

Au démarrage, l'extension crée l'onglet `STRUCTURE JHR` dans l'espace de travail Conception, puis quatre panneaux propres au complément. Le panneau `CRÉER` reçoit la commande principale de profil et le gestionnaire de DXF personnels. Le panneau `MODIFIER` reçoit les jonctions acier, le grugeage et l'inspecteur. Le panneau `ASSEMBLAGES` reçoit les assemblages composés en cours de validation. Le panneau `PARAMÈTRES` reçoit les réglages locaux. Les définitions de commandes restent indépendantes de leur emplacement afin que cette organisation n'altère aucune fonction géométrique.

L'onglet et les panneaux utilisent des identifiants stables et sont réutilisés s'ils existent déjà. À l'arrêt, les commandes retirent d'abord leurs boutons et leurs définitions, puis l'extension supprime ses panneaux et son onglet. Aucun panneau natif de Fusion n'est supprimé.

## Principe

Le squelette reste dans le composant racine. Pour chaque ligne ou arc sélectionné, la commande crée un nouveau composant contenant sa propre section et son propre corps.

```text
Composant racine
├── Esquisse du squelette
│   └── Ligne sélectionnée
└── BARRE_HEA160_001
    ├── PLAN_PROFIL_MILIEU
    ├── ESQUISSE_HEA160_DXF_ANCRAGE_TL
    ├── BARRE_CENTREE_SUR_CHEMIN
    └── CORPS_HEA160
```

Le plan de section est normal au chemin et placé à la distance normalisée `0.5`. Le vrai DXF sélectionné est importé sur ce plan dans une esquisse unique. Son contour n'est ni redessiné ni simplifié. Un décalage d'import place le point d'ancrage choisi sur l'origine de l'esquisse. Après contrôle des dimensions et de cet ancrage, les axes réels de l'esquisse sont comparés au repère transversal du chemin utilisé par l'aperçu. Le changement de base nécessaire est composé avec la rotation et les miroirs, puis appliqué autour de l'axe Z local passant par l'origine. Le balayage utilise le chemin complet : la section se trouve donc au milieu de sa longueur et se développe vers ses deux extrémités.

L'API Fusion interdit l'import DXF depuis les événements d'une commande. La commande enregistre donc les chemins, le profil et l'ancrage choisis, puis déclenche un événement personnalisé mis en file. Fusion exécute l'import lorsque l'interface redevient disponible. Avant le balayage, l'extension compare les dimensions importées aux limites calculées dans le DXF, contrôle la position de l'ancrage et exige au moins une région fermée.

Pour un tube, Fusion peut exposer le disque intérieur et la matière annulaire comme deux régions distinctes. L'extension choisit la région qui contient le plus de boucles afin de balayer la matière avec son vide intérieur.

## Aperçu dynamique

Pendant que la commande est ouverte, l'événement `executePreview` et les changements d'entrées rafraîchissent un maillage graphique jaune semi-transparent dans le composant racine. Le second chemin garantit l'affichage même si un chemin occupé maintient volontairement le bouton `OK` désactivé. Tous les contours du DXF choisi sont lus : lignes, arcs, cercles et polylignes, y compris les contours intérieurs. Les arcs sont discrétisés uniquement pour l'affichage. Cet aperçu n'est pas une entité CAO : il ne crée ni composant, ni esquisse, ni corps, ni entrée d'historique. Il est supprimé avant l'exécution finale et lors de l'annulation.

Le résultat final reste exclusivement créé par l'import direct du DXF, puis par le balayage Fusion. La discrétisation graphique ne peut donc pas altérer la géométrie réelle.

## Points d'ancrage

Les neuf points sont calculés sur la boîte géométrique exacte du DXF : trois colonnes `gauche`, `centre`, `droite` et trois lignes `haut`, `milieu`, `bas`. La grille Fusion utilise neuf boutons à icône ; les huit positions disponibles sont bleues et la position active est rouge. Le centre `C` reste sélectionné au démarrage pour conserver le comportement des versions précédentes.

Le même point source est soustrait aux coordonnées de l'aperçu et utilisé comme décalage de l'import DXF final. La rotation de l'aperçu puis celle de l'esquisse finale utilisent toutes deux cette origine. Le changement de base entre le plan choisi automatiquement par Fusion et le repère du chemin ne contient aucune translation : le point d'ancrage reste donc exactement sur l'origine.

## Rotation

L'interface accepte un angle affiché en degrés ; l'API Fusion le fournit en radians. Deux boutons permettent aussi d'inverser séparément les coordonnées locales X et Y. Les miroirs sont toujours calculés avant la rotation, autour de `(0, 0)` après application de l'ancrage.

La matrice 2D de rotation et de miroirs est commune à l'aperçu et au résultat final. Pour l'esquisse DXF importée, elle est précédée du changement de base calculé depuis `Sketch.xDirection` et `Sketch.yDirection`, puis étendue en matrice 3D de déterminant positif. La matrice composée est appliquée en une fois à toutes les lignes, tous les arcs et tous les cercles. Les courbes exactes du DXF sont donc conservées : seule leur orientation change.

## Paramétrage actuel

| Paramètre | V1 |
|---|---|
| Profil | 341 DXF normalisés par catégorie/zone, plus les profils personnels locaux |
| Dimensions | celles du DXF sélectionné |
| Ancrage | 9 points sur l'enveloppe, `C` par défaut |
| Rotation | angle réglable autour de l'ancrage, `0°` par défaut |
| Miroirs | X et Y indépendants, désactivés par défaut |
| Matériau | acier disponible dans une bibliothèque physique chargée par Fusion |
| Chemin | une ligne ou un arc d'esquisse |
| Sortie | un composant et un corps par ligne |

## Traçabilité dans Fusion

Chaque nouveau composant reçoit les attributs `profile`, `profile_category`, `profile_region`, `profile_family`, `profile_source`, `anchor`, `rotation_deg`, `flip_x`, `flip_y`, `source_curve_token`, `source_curve_type` et `extension_version`. Les attributs `material_name`, `material_id`, `material_library_name`, `material_library_id`, `material_source_id` et `material_property_count` tracent le matériau physique. L'ancien attribut `source_line_token` est aussi conservé pour les lignes afin de maintenir la compatibilité avec la V1.0.1. Pour une barre ancienne, l'absence de catégorie et de zone est interprétée comme `Zones_geographiques` et `Europe`.

Avant une création, ces jetons permettent aussi de retrouver les barres déjà liées aux chemins sélectionnés. Sans demande explicite de remplacement, la validation est bloquée afin d'éviter deux corps superposés. Avec remplacement, la commande mémorise les anciennes occurrences, crée d'abord toutes les nouvelles barres, puis retire les anciennes seulement lorsque la phase de création est terminée. Un échec d'import ou de balayage laisse donc les anciennes barres en place.

## Inspection des barres existantes

Une seconde commande sélectionne uniquement une occurrence de composant. Elle lit les attributs du groupe `EI_JHR_StructuralMember`, les valide dans un module indépendant de l'API Fusion et refuse les composants qui ne possèdent pas les informations minimales attendues. Le chemin du DXF est accepté uniquement s'il reste relatif à la bibliothèque.

Le jeton `source_curve_token`, ou l'ancien `source_line_token`, est transmis à `Design.findEntityByToken`. La commande indique ainsi si la ligne ou l'arc du squelette est toujours retrouvé. Cette première phase est strictement en lecture seule : elle ne supprime ni ne recrée aucune entité Fusion.

## Matériau physique Fusion

À l'ouverture de la commande, la V1.9.7 parcourt `Application.materialLibraries`, les matériaux de chaque bibliothèque disponible et les matériaux propres au document actif. Elle conserve uniquement les entrées dont le nom ou la description indique un acier dans les langues usuelles, ou une nuance structurale S235/S275/S355/S420/S460, et qui exposent au moins une propriété physique. Les matériaux du document sont affichés en premier ; le S235JR EI_JHR est sélectionné par défaut. Les matériaux de bibliothèque sont distingués par leur identifiant Autodesk. Dans le document actif, chaque entrée conserve aussi son index et son nom exact, car plusieurs copies peuvent partager le même identifiant interne. Le menu affiche toujours le nom fourni par Fusion avec le nom de sa source. Si aucune entrée exploitable n'est trouvée, la commande s'arrête avec un message clair.

Le choix est mémorisé par les identifiants internes de la bibliothèque et du matériau. Au moment de la création différée, ces identifiants sont résolus de nouveau ; le matériau obtenu est affecté directement à `BRepBody.material`. L'extension relit ensuite le matériau sur le corps et refuse la création si Fusion ne conserve pas un matériau valide ou si aucune propriété physique n'est disponible.

L'inspection compare l'identifiant enregistré à celui que Fusion relit réellement sur le corps. Elle affiche `OK` seulement en cas de concordance. L'ancien attribut texte `steel_grade`, éventuellement présent sur une barre candidate antérieure, reste lisible mais n'est jamais présenté comme la preuve d'une affectation physique.

Cette méthode garantit que le matériau sélectionné existe réellement dans Fusion. Elle ne transforme pas automatiquement une famille géométrique en S235 ou S355 et ne garantit pas qu'une nuance absente de la bibliothèque possède toutes les propriétés exigées par chaque solveur ; cette adéquation doit être contrôlée dans la fiche du matériau ou l'étude de simulation concernée.

### Nuances européennes créées dans le document

Au démarrage, `structural_materials.ensure_required_materials` recherche par nom exact les matériaux `S235JR EN 10025-2 - t<=16 mm`, `S275JR EN 10025-2 - t<=16 mm` et `S355J2 EN 10025-2 - t<=16 mm` dans `Design.materials`. Une seconde vérification a lieu à l'ouverture de la commande afin de couvrir un document créé après le démarrage du complément.

Si une nuance est absente, un acier générique réel des bibliothèques chargées est copié dans le document avec `Design.materials.addByCopy`. Le nom demandé est ensuite réappliqué et relu explicitement pour couvrir les versions de Fusion qui conservent d'abord le nom du matériau modèle. Les cinq propriétés indispensables à cette première étude linéaire sont identifiées par leurs identifiants internes ou leurs noms Fusion, puis converties vers l'unité déclarée par chaque propriété. Le nom et les valeurs sont immédiatement relus. Toute création incomplète est supprimée avant d'être utilisée.

Un matériau existant et conforme n'est jamais réécrit. S'il porte le nom réservé mais contient des valeurs différentes, le démarrage est refusé avec une erreur claire afin de ne pas remplacer silencieusement une fiche créée par l'utilisateur.

La portée est volontairement limitée au document : l'API publique `Materials.addByCopy` ne sait pas copier un matériau vers une bibliothèque globale. Les trois nuances apparaissent donc dans le menu sous la source `Document actif` et sont recréées, si nécessaire, dans chaque nouveau document utilisé avec l'extension.

## Lecture de la bibliothèque

La V1 cherche le dossier `profiles` par deux chemins relatifs seulement : d'abord dans une installation autonome du complément, puis dans le dépôt de développement. Aucun chemin propre à une machine n'est codé. Les profils normalisés suivent `profiles/Zones_geographiques/<zone>/<famille>/<profil>.dxf`. Les zones, familles et sections proposées sont découvertes dans cette bibliothèque au moment où la commande s'ouvre ; une installation autonome doit donc embarquer le dossier `profiles` complet.

Les anciens chemins `profiles/<famille>/<profil>.dxf` et le chemin transitoire `profiles/<zone>/<famille>/<profil>.dxf` restent résolus vers la zone Europe. La catégorie `Personnalisés` est une branche logique sœur de `Zones_geographiques` et n'est pas assimilée à une région.

### Bibliothèque personnelle locale

La catégorie `Personnalisés` n'est pas une zone géographique. Son pseudo-emplacement interne `Local` permet de réutiliser le filtrage catégorie/famille/section, mais le champ de zone est masqué dans l'interface. Les fichiers sont conservés hors de l'installation du complément dans `%APPDATA%\EI_JHR\fusion-free-structure\profiles\Personnalises` afin qu'une mise à jour du code ne les remplace pas et qu'ils ne soient jamais publiés avec le dépôt.

Chaque DXF possède un fichier JSON voisin contenant uniquement son nom de famille, sa désignation, son unité déclarée, son empreinte et sa date d'import. Fusion enregistre dans la barre un chemin logique relatif `profiles/Personnalises/<famille>/<profil>.dxf` ; ce chemin est résolu vers le dossier local uniquement après contrôle de sa portée.

L'ajout valide le DXF avant de le copier et vérifie que la copie est identique à la source. L'origine du fichier n'est pas déplacée : comme pour les profils normalisés, les neuf ancrages sont calculés à partir de l'enveloppe géométrique exacte, puis l'ancrage choisi est placé sur le chemin lors de la création.

La suppression est limitée à cette branche locale. Le DXF, son JSON et un enregistrement de suppression sont déplacés ensemble dans `corbeille_profils/<horodatage>-<profil>`. Les composants Fusion existants ne sont pas effacés ; leur attribut `profile_source` permet d'avertir l'utilisateur avant le retrait du fichier.

## Paramètres locaux

La V1.21.0 ajoute `%APPDATA%\EI_JHR\fusion-free-structure\settings.json`. Ce fichier est extérieur à l'installation du complément : une mise à jour du code ou des 341 DXF ne le remplace donc pas. Il ne contient que la version de son schéma et des distances en millimètres.

Les valeurs de jonction ajustée sont indexées par famille secondaire regroupée en quatre ensembles : IPE/HEA/HEB, cornières/tés, tubes et autres profils. Les deux moteurs de grugeage possèdent leurs propres valeurs. À l'ouverture d'une commande, le fichier est lu une seule fois ; lorsque la secondaire est sélectionnée, les champs reçoivent les valeurs de son groupe. Une modification ponctuelle dans la commande ne modifie pas le fichier : seule la validation par `OK` de `Paramètres Structure JHR` l'écrit.

L'écriture utilise un fichier temporaire puis un remplacement atomique. Une valeur négative, non numérique ou non finie est refusée. Si le JSON local est absent, les valeurs historiques sont utilisées. S'il est illisible, les commandes utilisent aussi ces valeurs d'usine, tandis que la fenêtre Paramètres affiche l'avertissement et demande une validation explicite avant de remplacer le fichier.

## Modèle général des jonctions

La géométrie de référence est le squelette, pas l'état de contact des solides. La commande retrouve les courbes sources enregistrées sur les composants, détermine l'extrémité concernée, la direction orientée depuis l'intérieur vers la rencontre et l'angle réel entre les axes. Les angles presque parallèles, inférieurs à `5°`, restent refusés car ils ne définissent pas un plan de coupe stable.

Pour une `Jonction ajustée`, la barre 1 est une référence intacte et la barre 2 est ajustée. La normale du plan est la projection de la direction intérieure de la barre 2 sur le plan perpendiculaire à l'axe de la barre 1. Cette construction ne suppose aucun angle droit. Le support extérieur est recherché sur les arêtes réelles du corps de référence avec une discrétisation maximale de `0,0001 mm`, puis conservé comme point paramétrique lié à l'arête. Le jeu décale le plan vers l'extérieur.

Pour une `Coupe d'onglet symétrique`, aucune barre n'est principale. Les directions des deux barres sont orientées vers la rencontre et la normale commune est leur différence normalisée. Le point de preview est calculé comme un point de l'intersection exacte des deux plans normaux aux axes. Dans chacun des composants, Fusion reconstruit ces deux plans, leur axe d'intersection et le même plan angulaire.

## Espace, chevauchement et prolongement

Chaque corps est classé par rapport au plan résolu :

- `overlap` : le corps traverse le plan et doit être séparé ;
- `aligned` : sa limite est déjà sur le plan et aucune matière n'est modifiée ;
- `gap` : le corps reste du côté intérieur et sa face d'extrémité doit être prolongée ;
- `outside` : le corps est entièrement du mauvais côté, ce qui signale une sélection ou une orientation incohérente.

La face plane dont la normale sortante correspond à la direction d'approche est contrôlée point par point. Si une partie de cette face n'a pas encore dépassé le plan, elle est extrudée en opération `Joindre`, même lorsque le reste du corps chevauche déjà le plan. La distance fait passer toute la face de l'autre côté, avec une marge géométrique de `0,5 mm`. Comme le sens positif d'une surface B-Rep n'est pas garanti dans le repère mondial, le complément essaie les deux directions de manière réversible et relit la face réellement obtenue. Seule une direction plaçant toute la face au-delà du plan est conservée. Le corps est ensuite séparé et toutes les parties extérieures sont retirées.

La prévisualisation et la création partagent `cut_point` et `cut_normal`. Après création de chaque plan Fusion, son orientation et sa distance au point de preview sont contrôlées ; une différence supérieure à `0,01 mm` annule l'opération avant la coupe.

Pour une jonction ajustée, la principale n'est plus supposée infinie le long de son axe. Le contour de la face d'extrémité secondaire est projeté le long de sa direction réelle jusqu'au plan de contact. L'intervalle obtenu sur l'axe principal est comparé aux limites du corps principal. Si une extrémité ne couvre pas cet intervalle, sa face est prolongée de la valeur exacte avant de couper la secondaire. Cette projection inclut automatiquement la section, la rotation, les miroirs, l'ancrage et l'angle entre les deux barres.

## Opérations multiples

Le groupe `EI_JHR_StructuralJoint` n'est plus un verrou binaire. Chaque traitement ajoute un JSON indépendant `operation_0001`, `operation_0002`, etc. contenant notamment le type, l'indice d'extrémité `0` ou `1`, l'autre composant, les courbes sources, l'angle, le jeu, l'état initial et le prolongement. Une barre peut donc recevoir une opération à chaque extrémité et d'autres traitements tant que sa géométrie courante permet la fonction demandée. Les anciens attributs fixes sont conservés mais ne bloquent plus les nouvelles opérations.

Une barre de référence cintrée, les onglets sur arcs, les grugeages sur chemins cintrés, les mélanges I/H ↔ cornière/té, les platines et les boulons restent en dehors de cette étape.

## Grugeage des profils ouverts

La V1.17 a introduit la prévisualisation, la V1.18.0 a créé le premier grugeage IPE réel à `90°` et la V1.19.0 généralise la même commande aux secondaires IPE, HEA et HEB ainsi qu'aux angles non parallèles supérieurs à `5°`. Les deux barres restent droites et leurs axes doivent se rejoindre.

Les limites des deux semelles et de l'âme sont déduites du contour fermé du DXF source de la secondaire. La position des deux volumes tient ensuite compte du point d'ancrage enregistré, de la rotation et des miroirs appliqués lors de la création de la barre. À un angle oblique, les intersections de la face extérieure principale avec les deux côtés de la secondaire n'ont pas la même profondeur. Le calcul projette donc tous les coins des deux zones de semelle vers cette face et retient la profondeur maximale, augmentée du jeu longitudinal.

La V1.17.1 localise aussi les deux faces de l'âme principale dans son DXF. Elle choisit celle qui regarde la secondaire, la décale du `Jeu contre l'âme` et obtient ainsi le plan de coupe droite de l'extrémité secondaire. Si la principale se termine trop près du raccord, la face secondaire est projetée sur ce plan et sa portée est comparée au corps principal, comme dans la jonction droite. Chaque manque de couverture fournit le côté et la longueur du prolongement requis.

Deux volumes rouges semi-transparents montrent les semelles proposées au retrait. Leurs quatre sommets de départ sont projetés sur le plan de la face extérieure principale et leurs quatre sommets d'arrivée sur le plan réel de l'âme. Ces deux limites parallèles suivent donc le même angle, y compris lorsque la secondaire est oblique. Un carré orange montre le plan de l'âme et une section verte montre chaque prolongement nécessaire de la principale. Ces graphismes restent temporaires et ne créent aucune entrée d'historique avant la validation.

Après `OK`, la secondaire reçoit les plans de station des deux chemins. Leur intersection produit `AXE_ORIENTATION_COUPE_AME`, autour duquel Fusion construit `PLAN_ORIENTATION_AME_PRINCIPALE`. Ce plan est décalé une première fois sur la face extérieure pour produire `PLAN_DEBUT_GRUGEAGE`, puis une seconde fois sur l'âme pour produire `PLAN_COUPE_AME_PRINCIPALE`. `PLAN_REFERENCE_ESQUISSE_GRUGEAGE`, normal au chemin secondaire, est placé derrière toute la limite de départ et porte seulement les deux rectangles fermés des zones de semelle. L'extrusion utilise la première limite oblique comme départ réel et la seconde comme arrivée réelle. La principale est auparavant prolongée si sa couverture est insuffisante ; la secondaire est prolongée puis séparée sur le plan de l'âme si nécessaire.

La V1.20.0 applique le même moteur aux cornières et aux tés. Les deux plus longues faces verticales droites du contour DXF identifient la branche à conserver. La V1.20.1 sépare alors deux opérations uniquement pour ce groupe : le volume droit s'arrête sur la face supérieure exacte de la branche horizontale secondaire, puis un dégagement arrondi échappe le congé intérieur de la principale. Son rayon est le rayon détecté dans le DXF principal augmenté du jeu demandé. Une cornière extérieure ne déclenche aucun dégagement du côté sans congé ; un té peut en déclencher un des deux côtés. La preview matérialise séparément ces deux retraits rouges et la coupe finale applique le même rayon sur l'arête correspondante.

La V1.20.2 sépare aussi les deux jeux utilisateur. `Jeu sous l'âme secondaire` est ajouté à l'épaisseur de la branche pour placer la limite droite du retrait ; l'arête du dégagement arrondi suit exactement cette nouvelle hauteur. `Jeu autour du congé principal` est ajouté uniquement au rayon intérieur détecté sur la principale. Ces valeurs sont donc modifiables indépendamment et enregistrées séparément.

Cette séparation n'est jamais appliquée aux IPE, HEA et HEB : leur double grugeage, leurs deux volumes rouges et la signification de leur jeu vertical restent inchangés. La branche verticale d'une cornière ou d'un té principal fournit ses deux faces d'appui possibles, et l'orientation enregistrée détermine automatiquement celle qui regarde la secondaire.

Le périmètre V1.20.2 autorise les quatre combinaisons cornière/té et conserve séparément le mode I/H vers I/H. Les mélanges entre ces deux groupes sont refusés jusqu'à leur validation explicite. Les 46 cornières et 11 tés fournis passent le contrôle géométrique automatique.

L'extrusion désigne explicitement le corps secondaire participant. La création est acceptée seulement si un corps unique subsiste et si le volume retiré est mesurable. Les nouveaux traitements utilisent `open_profile_cope`, mais les anciens `double_ipe_cope` et `double_ih_cope` restent reconnus pour protéger les documents antérieurs. Un second grugeage reste possible à l'autre extrémité, tandis qu'un doublon sur la même extrémité est refusé. Si une étape échoue, l'attribut et toutes les entités créées pendant la tentative sont supprimés dans l'ordre inverse.

## Premier assemblage par doubles cornières

La V1.22.0 ajoute uniquement le calcul et l'affichage du premier assemblage composé. La principale et la secondaire doivent être deux IPE, HEA ou HEB droits, liés à deux axes se rejoignant à `90° ± 0,5°`. La commande réutilise les métadonnées de chaque barre, son DXF, son ancrage, sa rotation, ses miroirs et les repères de section déjà employés par le grugeage.

Le DXF de la cornière égale choisie est discrétisé seulement pour l'affichage puis son coin extérieur est ramené à l'origine locale. La face de l'âme principale tournée vers la secondaire est obtenue par le même calcul que la coupe de grugeage. Les deux faces de l'âme secondaire viennent directement des limites d'âme détectées dans son DXF. Le premier coin de cornière est posé sur la face négative, le second sur la face positive ; leurs axes transversaux sont opposés et leurs axes dirigés vers l'intérieur de la secondaire sont identiques. Leur hauteur est centrée sur le repère vertical de la secondaire, puis déplacée par le décalage saisi.

Le résultat V1.22.0 est un maillage jaune temporaire dans le composant racine. Il n'est pas sélectionnable et disparaît à l'annulation ou à la validation. Cette position ayant été validée dans Fusion, la V1.23.0 transforme chaque repère local en matrice directe : selon le côté de l'âme, l'origine est placée en bas ou en haut afin que l'extrusion locale `+Z` reproduise toujours exactement la hauteur affichée. Le DXF original est importé sur le plan XY local avec l'ancrage `BL`, puis extrudé sans reconstruire ni simplifier son contour. Comme Fusion peut ignorer le décalage d'import sur un composant déjà orienté, la V1.23.1 mesure l'enveloppe locale obtenue, translate toutes les courbes jusqu'à `BL`, puis relance le contrôle strict avant l'extrusion. En V1.23.2, les fonctions dont l'esquisse et le corps appartiennent déjà à ce composant restent entièrement locales : la matrice de l'occurrence est l'unique transformation vers l'assemblage. Cette suppression du contexte redondant n'a cependant pas suffi tant que l'import avait lieu dans une occurrence déjà transformée.

La V1.23.3 crée donc chaque composant à l'identité. Le DXF, l'extrusion et les deux groupes de trous sont terminés dans le plan XY et les axes XYZ locaux. Les centres monde qui dessinent les cercles rouges sont projetés mathématiquement dans ce repère rigide, puis les mêmes coordonnées locales alimentent les fonctions de perçage. La position initiale de l'occurrence terminée reçoit ensuite la matrice du repère validé par l'aperçu. Enfin, l'enveloppe précise obtenue dans l'assemblage est comparée aux huit coins attendus du prisme local ; toute divergence déclenche le retrait complet de la tentative.

Le motif de perçage est centré dans la hauteur des cornières. Son diamètre, son nombre de rangées, son entraxe vertical et ses distances depuis le coin extérieur sur les deux branches sont explicites. Le même calcul produit les cercles rouges de preview, les trous des deux cornières, deux colonnes dans l'âme principale et une rangée traversante dans l'âme secondaire. Avant `OK`, le complément vérifie le contour de la cornière et les hauteurs libres des deux âmes. Après `OK`, chaque groupe de trous est une fonction traversante limitée à son corps. Une erreur supprime d'abord les fonctions ajoutées aux barres, puis les deux occurrences de cornière. Les composants conservent seulement des chemins DXF relatifs et les valeurs de dessin ; aucun boulon ni calcul de résistance n'est ajouté dans cette version.
