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

Le plan de section est normal à la ligne et placé à la distance normalisée `0.5`. Le profil est centré sur l'origine de ce plan. Le balayage utilise la ligne complète comme chemin : la section se trouve donc au centre et le volume se développe vers les deux extrémités.

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

## Choix de sécurité

La V1 n'ouvre aucun DXF à l'exécution : le contour IPE 100 validé est exprimé directement sous forme de segments et d'arcs. L'intégration future du lecteur de bibliothèque devra rester relative au dépôt et valider strictement les fichiers avant de créer de la géométrie.
