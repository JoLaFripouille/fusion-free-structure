# fusion-free-structure

Extension Autodesk Fusion en cours de développement pour créer des profils acier le long de lignes ou d'arcs d'un squelette paramétrique.

La V1 est volontairement limitée afin de valider progressivement la création, l'interface et l'orientation avant d'ajouter les jonctions.

## Fonction de la V1

- sélection d'une ou plusieurs lignes ou arcs d'esquisse dans le composant racine ;
- choix de la famille puis de la section parmi les 341 DXF disponibles ;
- version exacte chargée visible dans le nom du bouton et dans la fenêtre de commande ;
- création d'une barre droite ou cintrée par chemin avec le profil choisi ;
- import direct du DXF sélectionné, sans reconstruction manuelle du contour ;
- aperçu graphique jaune et semi-transparent, mis à jour avec la sélection du chemin ou du profil ;
- choix visuel parmi neuf points d'ancrage, avec les points disponibles en bleu et le point actif en rouge ;
- section placée sur le chemin par l'ancrage choisi, avec le centre `C` et une rotation de `0°` par défaut ;
- angle réglable en degrés autour de l'ancrage, avec aperçu jaune mis à jour avant validation ;
- boutons `Miroir X` et `Miroir Y`, indépendants et cumulables autour du même ancrage ;
- un composant indépendant par barre ;
- une esquisse de section et un corps dans chaque composant ;
- dépendance paramétrique native au squelette grâce à un balayage sur la ligne complète.

## Bibliothèque incluse

Le dossier [`profiles`](profiles/) contient 341 profils DXF R12 à l'échelle 1:1, suivant la convention millimétrique validée lors de l'extraction, répartis uniquement dans les 12 familles réellement détectées. Les listes de l'extension sont produites directement depuis ces dossiers. Le DXF R12 ne stocke pas le champ moderne `$INSUNITS` : l'application importatrice doit donc être réglée en millimètres.

| Famille | Nombre |
|---|---:|
| Cornière égale | 28 |
| Cornière inégale | 18 |
| HEA | 15 |
| HEB | 15 |
| IPE | 18 |
| IPN | 10 |
| Té égal | 11 |
| Tube carré | 65 |
| Tube rectangulaire | 92 |
| Tube rond | 41 |
| UPE | 14 |
| UPN | 14 |
| **Total** | **341** |

Les chemins utilisés par le projet sont relatifs au dépôt. Aucun chemin propre à une machine ou à un compte utilisateur ne doit être ajouté au code.

## Organisation

```text
fusion-free-structure/
├── addin/JHR_StructuralMembers_V1/  # extension Fusion
├── profiles/                        # bibliothèque DXF
├── tests/                           # contrôles hors Fusion
├── docs/                            # architecture et protocole d'essai
├── CHANGELOG.md                     # historique des versions
├── KNOWN_ISSUES.md                  # problèmes identifiés
└── ROADMAP.md                       # améliorations prévues
```

## Installation de développement

Dans Fusion, ouvrir **Utilitaires > Scripts et compléments**, puis ajouter le dossier relatif :

```text
addin/JHR_StructuralMembers_V1
```

La V1 doit d'abord être testée dans un nouveau document paramétrique. Le protocole exact est décrit dans [`docs/TEST_PROTOCOL_FUSION.md`](docs/TEST_PROTOCOL_FUSION.md).

## Vérifications hors Fusion

Depuis la racine du dépôt :

```text
python -B -m unittest discover -s tests -v
```

## Suivi obligatoire

Toute modification fonctionnelle doit :

1. mettre à jour `VERSION` et la version du manifeste quand une livraison est créée ;
2. ajouter une entrée dans `CHANGELOG.md` ;
3. consigner tout problème confirmé dans `KNOWN_ISSUES.md` ;
4. consigner toute amélioration retenue dans `ROADMAP.md` ;
5. exécuter les tests avant publication.

L'option `-B` évite de générer du bytecode contenant des chemins locaux dans le dossier destiné à la publication.

## Licence

Aucune licence de réutilisation n'est encore choisie. Le dépôt peut être consulté publiquement, mais les conditions de réutilisation devront être validées avant une diffusion stable.
