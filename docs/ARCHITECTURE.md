# Architecture de la V1

## Principe

Le squelette reste dans le composant racine. Pour chaque ligne sélectionnée, la commande crée un nouveau composant contenant sa propre section et son propre corps.

```text
Composant racine
├── Esquisse du squelette
│   └── Ligne sélectionnée
└── BARRE_IPE100_001
    ├── PLAN_PROFIL_MILIEU
    ├── ESQUISSE_IPE100_ANCRAGE_C
    ├── BARRE_SYMETRIQUE_SUR_LIGNE
    └── CORPS_IPE100
```

Le plan de section est normal à la ligne et placé à la distance normalisée `0.5`. Le vrai fichier `profiles/IPE/IPE_100.dxf` est importé sur ce plan dans une esquisse unique. Son contour n'est ni redessiné ni simplifié. Un décalage d'import place l'ancrage central `C` sur l'origine de l'esquisse. Le balayage utilise la ligne complète comme chemin : la section se trouve donc au centre et le volume se développe vers les deux extrémités.

L'API Fusion interdit l'import DXF depuis les événements d'une commande. La commande enregistre donc la sélection, puis déclenche un événement personnalisé mis en file. Fusion exécute l'import lorsque l'interface redevient disponible. Avant le balayage, l'extension contrôle automatiquement une section de `55 × 100 mm`, centrée, fermée et composée d'un profil unique.

## Paramétrage actuel

| Paramètre | V1 |
|---|---|
| Profil | IPE 100 |
| Dimensions | 55 × 100 mm |
| Ancrage | C, centre de section |
| Rotation | 0° |
| Chemin | une ligne droite d'esquisse |
| Sortie | un composant et un corps par ligne |

## Traçabilité dans Fusion

Chaque composant reçoit les attributs `profile`, `anchor`, `rotation_deg`, `source_line_token` et `extension_version`. Ils préparent les futures commandes d'édition sans dépendre du nom affiché dans l'arborescence.

## Lecture de la bibliothèque

La V1 cherche le DXF par deux chemins relatifs seulement : d'abord dans une installation autonome du complément, puis dans le dossier `profiles` du dépôt de développement. Aucun chemin propre à une machine n'est codé. Une copie autonome doit donc contenir `profiles/IPE/IPE_100.dxf` dans son dossier de complément.
