# Sécurité

## Périmètre

La V1 fonctionne localement dans Autodesk Fusion. Elle n'utilise pas le réseau, ne lance pas de programme externe et ne demande aucun identifiant.

## Signaler un problème

Ne pas publier de donnée sensible dans une issue publique. Utiliser en priorité le signalement privé de vulnérabilité proposé dans l'onglet **Security** du dépôt GitHub.

Le signalement doit préciser la version, le fichier concerné, les étapes minimales de reproduction et l'impact observé.

## Règles du dépôt

- aucun secret, jeton, identifiant ou chemin personnel dans le code ou les exemples ;
- chemins relatifs uniquement ;
- aucun téléchargement ou exécution automatique de contenu externe ;
- toute future lecture de DXF devra traiter le fichier comme une entrée non fiable et imposer des limites de taille et de complexité ;
- contrôle de sécurité avant chaque publication publique.
