# Historique des versions

Toutes les évolutions livrées de `fusion-free-structure` sont consignées ici.

## [Non publié]

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
