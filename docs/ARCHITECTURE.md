# Architecture de la V1

## Interface Fusion dédiée

Au démarrage, l'extension crée l'onglet `STRUCTURE JHR` dans l'espace de travail Conception, puis deux panneaux propres au complément. Le panneau `CRÉER` reçoit la commande principale de profil et le gestionnaire de DXF personnels. Le panneau `MODIFIER` reçoit les jonctions acier et l'inspecteur. Les définitions de commandes restent indépendantes de leur emplacement afin que cette organisation n'altère aucune fonction géométrique.

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

La face plane dont la normale sortante correspond à la direction d'approche est contrôlée point par point. Si une partie de cette face n'a pas encore dépassé le plan, elle est extrudée en opération `Joindre`, même lorsque le reste du corps chevauche déjà le plan. La distance fait passer toute la face de l'autre côté, avec une marge géométrique de `0,5 mm`. Le corps obtenu est ensuite séparé et toutes les parties extérieures sont retirées. Le prolongement est omis seulement lorsque toute la face d'extrémité dépasse déjà le plan.

La prévisualisation et la création partagent `cut_point` et `cut_normal`. Après création de chaque plan Fusion, son orientation et sa distance au point de preview sont contrôlées ; une différence supérieure à `0,01 mm` annule l'opération avant la coupe.

## Opérations multiples

Le groupe `EI_JHR_StructuralJoint` n'est plus un verrou binaire. Chaque traitement ajoute un JSON indépendant `operation_0001`, `operation_0002`, etc. contenant notamment le type, l'indice d'extrémité `0` ou `1`, l'autre composant, les courbes sources, l'angle, le jeu, l'état initial et le prolongement. Une barre peut donc recevoir une opération à chaque extrémité et d'autres traitements tant que sa géométrie courante permet la fonction demandée. Les anciens attributs fixes sont conservés mais ne bloquent plus les nouvelles opérations.

Une barre de référence cintrée, les onglets sur arcs, les grugeages, platines et boulons restent en dehors de cette étape.
