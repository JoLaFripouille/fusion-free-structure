# Architecture de la V1

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

Le plan de section est normal au chemin et placé à la distance normalisée `0.5`. Le vrai DXF sélectionné est importé sur ce plan dans une esquisse unique. Son contour n'est ni redessiné ni simplifié. Un décalage d'import place le point d'ancrage choisi sur l'origine de l'esquisse. Après contrôle des dimensions et de cet ancrage, les courbes importées sont pivotées autour de l'axe Z local passant par l'origine. Le balayage utilise le chemin complet : la section se trouve donc au milieu de sa longueur et se développe vers ses deux extrémités.

L'API Fusion interdit l'import DXF depuis les événements d'une commande. La commande enregistre donc les chemins, le profil et l'ancrage choisis, puis déclenche un événement personnalisé mis en file. Fusion exécute l'import lorsque l'interface redevient disponible. Avant le balayage, l'extension compare les dimensions importées aux limites calculées dans le DXF, contrôle la position de l'ancrage et exige au moins une région fermée.

Pour un tube, Fusion peut exposer le disque intérieur et la matière annulaire comme deux régions distinctes. L'extension choisit la région qui contient le plus de boucles afin de balayer la matière avec son vide intérieur.

## Aperçu dynamique

Pendant que la commande est ouverte, l'événement `executePreview` dessine un maillage graphique jaune semi-transparent dans le composant racine. Tous les contours du DXF choisi sont lus : lignes, arcs, cercles et polylignes, y compris les contours intérieurs. Les arcs sont discrétisés uniquement pour l'affichage. Cet aperçu n'est pas une entité CAO : il ne crée ni composant, ni esquisse, ni corps, ni entrée d'historique. Il est supprimé avant l'exécution finale et lors de l'annulation.

Le résultat final reste exclusivement créé par l'import direct du DXF, puis par le balayage Fusion. La discrétisation graphique ne peut donc pas altérer la géométrie réelle.

## Points d'ancrage

Les neuf points sont calculés sur la boîte géométrique exacte du DXF : trois colonnes `gauche`, `centre`, `droite` et trois lignes `haut`, `milieu`, `bas`. La grille Fusion utilise neuf boutons à icône ; les huit positions disponibles sont bleues et la position active est rouge. Le centre `C` reste sélectionné au démarrage pour conserver le comportement des versions précédentes.

Le même point source est soustrait aux coordonnées de l'aperçu et utilisé comme décalage de l'import DXF final. La rotation de l'aperçu puis celle de l'esquisse finale utilisent toutes deux cette origine. L'aperçu et le corps ne peuvent donc pas employer deux conventions de pivot différentes.

## Rotation

L'interface accepte un angle affiché en degrés ; l'API Fusion le fournit en radians. Deux boutons permettent aussi d'inverser séparément les coordonnées locales X et Y. Les miroirs sont toujours calculés avant la rotation, autour de `(0, 0)` après application de l'ancrage.

Une seule matrice 2D est calculée pour l'aperçu et pour le résultat final. Dans l'esquisse DXF importée, elle est étendue en matrice 3D de déterminant positif puis appliquée en une fois à toutes les lignes, tous les arcs et tous les cercles. Les courbes exactes du DXF sont donc conservées : seule leur orientation change.

## Paramétrage actuel

| Paramètre | V1 |
|---|---|
| Profil | famille puis section parmi 341 DXF |
| Dimensions | celles du DXF sélectionné |
| Ancrage | 9 points sur l'enveloppe, `C` par défaut |
| Rotation | angle réglable autour de l'ancrage, `0°` par défaut |
| Miroirs | X et Y indépendants, désactivés par défaut |
| Matériau | acier disponible dans une bibliothèque physique chargée par Fusion |
| Chemin | une ligne ou un arc d'esquisse |
| Sortie | un composant et un corps par ligne |

## Traçabilité dans Fusion

Chaque nouveau composant reçoit les attributs `profile`, `profile_family`, `profile_source`, `anchor`, `rotation_deg`, `flip_x`, `flip_y`, `source_curve_token`, `source_curve_type` et `extension_version`. Les attributs `material_name`, `material_id`, `material_library_name`, `material_library_id`, `material_source_id` et `material_property_count` tracent le matériau physique. L'ancien attribut `source_line_token` est aussi conservé pour les lignes afin de maintenir la compatibilité avec la V1.0.1.

## Inspection des barres existantes

Une seconde commande sélectionne uniquement une occurrence de composant. Elle lit les attributs du groupe `EI_JHR_StructuralMember`, les valide dans un module indépendant de l'API Fusion et refuse les composants qui ne possèdent pas les informations minimales attendues. Le chemin du DXF est accepté uniquement s'il reste relatif à la bibliothèque.

Le jeton `source_curve_token`, ou l'ancien `source_line_token`, est transmis à `Design.findEntityByToken`. La commande indique ainsi si la ligne ou l'arc du squelette est toujours retrouvé. Cette première phase est strictement en lecture seule : elle ne supprime ni ne recrée aucune entité Fusion.

## Matériau physique Fusion

À l'ouverture de la commande, la V1.9.4 parcourt `Application.materialLibraries`, les matériaux de chaque bibliothèque disponible et les matériaux propres au document actif. Elle conserve uniquement les entrées dont le nom ou la description indique un acier dans les langues usuelles, ou une nuance structurale S235/S275/S355/S420/S460, et qui exposent au moins une propriété physique. Les matériaux du document sont affichés en premier ; le S235JR EI_JHR est sélectionné par défaut. Le menu affiche toujours le nom fourni par Fusion avec le nom de sa source. Si aucune entrée exploitable n'est trouvée, la commande s'arrête avec un message clair.

Le choix est mémorisé par les identifiants internes de la bibliothèque et du matériau. Au moment de la création différée, ces identifiants sont résolus de nouveau ; le matériau obtenu est affecté directement à `BRepBody.material`. L'extension relit ensuite le matériau sur le corps et refuse la création si Fusion ne conserve pas un matériau valide ou si aucune propriété physique n'est disponible.

L'inspection compare l'identifiant enregistré à celui que Fusion relit réellement sur le corps. Elle affiche `OK` seulement en cas de concordance. L'ancien attribut texte `steel_grade`, éventuellement présent sur une barre candidate antérieure, reste lisible mais n'est jamais présenté comme la preuve d'une affectation physique.

Cette méthode garantit que le matériau sélectionné existe réellement dans Fusion. Elle ne transforme pas automatiquement une famille géométrique en S235 ou S355 et ne garantit pas qu'une nuance absente de la bibliothèque possède toutes les propriétés exigées par chaque solveur ; cette adéquation doit être contrôlée dans la fiche du matériau ou l'étude de simulation concernée.

### Nuances européennes créées dans le document

Au démarrage, `structural_materials.ensure_required_materials` recherche par nom exact les matériaux `S235JR EN 10025-2 - t<=16 mm` et `S355J2 EN 10025-2 - t<=16 mm` dans `Design.materials`. Une seconde vérification a lieu à l'ouverture de la commande afin de couvrir un document créé après le démarrage du complément.

Si une nuance est absente, un acier générique réel des bibliothèques chargées est copié dans le document avec `Design.materials.addByCopy`. Les cinq propriétés indispensables à cette première étude linéaire sont identifiées par leurs identifiants internes ou leurs noms Fusion, puis converties vers l'unité déclarée par chaque propriété. Les valeurs sont immédiatement relues. Toute création incomplète est supprimée avant d'être utilisée.

Un matériau existant et conforme n'est jamais réécrit. S'il porte le nom réservé mais contient des valeurs différentes, le démarrage est refusé avec une erreur claire afin de ne pas remplacer silencieusement une fiche créée par l'utilisateur.

La portée est volontairement limitée au document : l'API publique `Materials.addByCopy` ne sait pas copier un matériau vers une bibliothèque globale. Les deux nuances apparaissent donc dans le menu sous la source `Document actif` et sont recréées, si nécessaire, dans chaque nouveau document utilisé avec l'extension.

## Lecture de la bibliothèque

La V1 cherche le dossier `profiles` par deux chemins relatifs seulement : d'abord dans une installation autonome du complément, puis dans le dépôt de développement. Aucun chemin propre à une machine n'est codé. Les familles et sections proposées sont découvertes dans cette bibliothèque au moment où la commande s'ouvre ; une installation autonome doit donc embarquer le dossier `profiles` complet.
