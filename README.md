# fusion-free-structure

Extension Autodesk Fusion en cours de développement pour créer des profils acier le long de lignes ou d'arcs d'un squelette paramétrique.

La V1 est volontairement limitée afin de valider progressivement la création, l'interface, l'orientation puis chaque type de jonction séparément.

## Fonction de la V1

- onglet Fusion dédié `STRUCTURE JHR`, divisé en groupes `CRÉER`, `MODIFIER`, `ASSEMBLAGES` et `PARAMÈTRES` ;
- sélection d'une ou plusieurs lignes ou arcs d'esquisse dans le composant racine ;
- choix de la catégorie, de la zone géographique, de la famille puis de la section parmi les 341 DXF disponibles ;
- ajout de profils DXF personnels dans une catégorie `Personnalisés` séparée des zones géographiques ;
- suppression récupérable des seuls profils personnels, avec avertissement s'ils sont utilisés dans le document actif ;
- détection des barres déjà présentes sur une ligne et remplacement explicite, sans créer de corps caché en doublon ;
- version exacte chargée visible dans le nom du bouton et dans la fenêtre de commande ;
- création d'une barre droite ou cintrée par chemin avec le profil choisi ;
- import direct du DXF sélectionné, sans reconstruction manuelle du contour ;
- aperçu graphique jaune et semi-transparent, mis à jour avec la sélection du chemin ou du profil ;
- choix visuel parmi neuf points d'ancrage, avec les points disponibles en bleu et le point actif en rouge ;
- section placée sur le chemin par l'ancrage choisi, avec le centre `C` et une rotation de `0°` par défaut ;
- angle réglable en degrés autour de l'ancrage, avec aperçu jaune mis à jour avant validation ;
- boutons `Miroir X` et `Miroir Y`, indépendants et cumulables autour du même ancrage ;
- inspection en lecture seule des paramètres enregistrés dans une barre existante et de sa liaison au squelette ;
- choix d'un matériau acier réellement disponible dans les bibliothèques chargées par Fusion, puis affectation physique au corps ;
- création contrôlée dans le document actif des nuances européennes `S235JR`, `S275JR` et `S355J2` pour la première comparaison de simulation ;
- un composant indépendant par barre ;
- une esquisse de section et un corps dans chaque composant ;
- dépendance paramétrique native au squelette grâce à un balayage sur la ligne complète.
- commande `Jonctions acier` : jonction ajustée à l'enveloppe d'une barre de référence, quel que soit l'angle non parallèle, ou coupe d'onglet symétrique entre deux barres droites ; détection des espaces et chevauchements, prolongement automatique, opérations multiples par barre et aperçu orange identique au plan final.
- commande `Grugeage profils ouverts` : double grugeage IPE/HEA/HEB ou grugeage simple pour les quatre combinaisons cornière/té, à tout angle non parallèle ; uniquement pour les cornières et les tés, le retrait droit suit l'épaisseur de la branche secondaire plus le `Jeu sous l'âme secondaire`, tandis qu'un réglage indépendant commande le dégagement rouge arrondi du congé principal. Le plan orange indique la face d'appui réelle et le vert son éventuel prolongement.
- commande `Assemblage par cornières` : deux cornières égales sont créées comme composants indépendants de part et d'autre de l'âme d'une secondaire IPE/HEA/HEB et contre l'âme d'une principale IPE/HEA/HEB, sur deux axes droits à `90°`. La section, la hauteur, le décalage vertical, le diamètre, le nombre de rangées, l'entraxe et les deux distances de perçage sont dynamiques. Les trous traversants sont alignés dans les deux cornières et les deux âmes. La V1.24.2 présélectionne ensuite les six positions et ouvre de manière différée la commande native `Insérer une attache` ; Fusion conserve ainsi le choix de la norme, de la longueur, du matériau et de la finition.
- commande `Paramètres Structure JHR` : onglet `Valeurs par défaut` sauvegardé localement, avec jeux distincts selon l'opération et le groupe de profils ; les valeurs sont proposées dans les commandes suivantes et restent modifiables pour une opération particulière.

Dans l'onglet dédié, `CRÉER` contient **Profil acier** et **Gérer les profils personnalisés**. `MODIFIER` contient **Jonctions acier**, **Grugeage profils ouverts** et **Inspecter un profil acier**. `ASSEMBLAGES` contient **Assemblage par cornières**. `PARAMÈTRES` contient **Paramètres Structure JHR**. Les commandes ne sont plus ajoutées aux panneaux généraux de Fusion.

## Bibliothèque incluse

Le dossier [`profiles`](profiles/) contient 341 profils DXF R12 à l'échelle 1:1, suivant la convention millimétrique validée lors de l'extraction. Ils sont classés sous la catégorie `Zones géographiques`, dans la zone `Europe`, puis dans les 12 familles réellement détectées. Les listes de l'extension sont produites directement depuis ces dossiers. Le DXF R12 ne stocke pas le champ moderne `$INSUNITS` : l'application importatrice doit donc être réglée en millimètres.

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

## Profils personnalisés

La commande **Gérer les profils personnalisés** accepte un DXF ASCII R12 dessiné en millimètres. Avant la copie, elle contrôle notamment la taille du fichier, les entités prises en charge, la fermeture des contours et les dimensions. Le DXF est copié sans modification dans les données locales de l'utilisateur, sous `%APPDATA%\EI_JHR\fusion-free-structure`, puis apparaît dans la catégorie `Personnalisés` à la prochaine ouverture de **Profil acier**.

Seuls les profils personnels peuvent être supprimés par cette commande. Une suppression déplace le DXF et ses métadonnées dans `corbeille_profils` au lieu de les effacer définitivement. Les barres déjà créées restent dans le document, mais l'inspecteur indiquera que le DXF source n'est plus disponible tant que le profil n'est pas restauré.

## Organisation

```text
fusion-free-structure/
├── addin/JHR_StructuralMembers_V1/  # extension Fusion
├── profiles/
│   └── Zones_geographiques/
│       └── Europe/                  # 12 familles, 341 DXF
├── tests/                           # contrôles hors Fusion
├── docs/                            # architecture et protocole d'essai
├── CHANGELOG.md                     # historique des versions
├── KNOWN_ISSUES.md                  # problèmes identifiés
└── ROADMAP.md                       # améliorations prévues
```

Les profils personnels ne figurent volontairement pas dans cette arborescence : ils restent dans les données locales de l'utilisateur.

Les valeurs par défaut sont également locales et ne sont jamais publiées dans le dépôt. Elles sont enregistrées dans `%APPDATA%\EI_JHR\fusion-free-structure\settings.json`.

## Installation dans Fusion

Le guide complet décrit le téléchargement depuis GitHub, les deux méthodes d'installation Windows, la copie indispensable de la bibliothèque DXF, le démarrage et la mise à jour :

**[Installer le complément dans Autodesk Fusion](docs/INSTALLATION_FUSION.md)**

Pour un premier essai, conserver l'arborescence GitHub complète puis ajouter dans **Utilitaires > Scripts et compléments > Compléments** le dossier :

```text
<dossier extrait>/fusion-free-structure/addin/JHR_StructuralMembers_V1
```

Ne pas copier uniquement ce sous-dossier sans suivre la méthode autonome du guide : sinon les 341 profils placés à la racine du dépôt ne seront pas trouvés.

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
