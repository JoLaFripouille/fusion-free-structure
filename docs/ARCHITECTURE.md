# Architecture de la V1

## Principe

Le squelette reste dans le composant racine. Pour chaque ligne ou arc sélectionné, la commande crée un nouveau composant contenant sa propre section et son propre corps.

```text
Composant racine
├── Esquisse du squelette
│   └── Ligne sélectionnée
└── BARRE_HEA160_001
    ├── PLAN_PROFIL_MILIEU
    ├── ESQUISSE_HEA160_DXF_ANCRAGE_C
    ├── BARRE_CENTREE_SUR_CHEMIN
    └── CORPS_HEA160
```

Le plan de section est normal au chemin et placé à la distance normalisée `0.5`. Le vrai DXF sélectionné est importé sur ce plan dans une esquisse unique. Son contour n'est ni redessiné ni simplifié. Un décalage d'import place le centre de sa boîte géométrique, nommé provisoirement `C`, sur l'origine de l'esquisse. Le balayage utilise le chemin complet : la section se trouve donc au centre et le volume se développe vers ses deux extrémités.

L'API Fusion interdit l'import DXF depuis les événements d'une commande. La commande enregistre donc les chemins et le profil choisis, puis déclenche un événement personnalisé mis en file. Fusion exécute l'import lorsque l'interface redevient disponible. Avant le balayage, l'extension compare les dimensions importées aux limites calculées dans le DXF, contrôle le centrage et exige au moins une région fermée.

Pour un tube, Fusion peut exposer le disque intérieur et la matière annulaire comme deux régions distinctes. L'extension choisit la région qui contient le plus de boucles afin de balayer la matière avec son vide intérieur.

## Aperçu dynamique

Pendant que la commande est ouverte, l'événement `executePreview` dessine un maillage graphique jaune semi-transparent dans le composant racine. Tous les contours du DXF choisi sont lus : lignes, arcs, cercles et polylignes, y compris les contours intérieurs. Les arcs sont discrétisés uniquement pour l'affichage. Cet aperçu n'est pas une entité CAO : il ne crée ni composant, ni esquisse, ni corps, ni entrée d'historique. Il est supprimé avant l'exécution finale et lors de l'annulation.

Le résultat final reste exclusivement créé par l'import direct du DXF, puis par le balayage Fusion. La discrétisation graphique ne peut donc pas altérer la géométrie réelle.

## Paramétrage actuel

| Paramètre | V1 |
|---|---|
| Profil | famille puis section parmi 341 DXF |
| Dimensions | celles du DXF sélectionné |
| Ancrage | C, centre de section |
| Rotation | 0° |
| Chemin | une ligne ou un arc d'esquisse |
| Sortie | un composant et un corps par ligne |

## Traçabilité dans Fusion

Chaque nouveau composant reçoit les attributs `profile`, `profile_family`, `profile_source`, `anchor`, `rotation_deg`, `source_curve_token`, `source_curve_type` et `extension_version`. L'ancien attribut `source_line_token` est aussi conservé pour les lignes afin de maintenir la compatibilité avec la V1.0.1.

## Lecture de la bibliothèque

La V1 cherche le dossier `profiles` par deux chemins relatifs seulement : d'abord dans une installation autonome du complément, puis dans le dépôt de développement. Aucun chemin propre à une machine n'est codé. Les familles et sections proposées sont découvertes dans cette bibliothèque au moment où la commande s'ouvre ; une installation autonome doit donc embarquer le dossier `profiles` complet.
