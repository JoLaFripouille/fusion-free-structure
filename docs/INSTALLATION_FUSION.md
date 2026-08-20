# Installer fusion-free-structure dans Autodesk Fusion

Ce guide concerne Windows et l'installation du complément publié sur GitHub. Aucun logiciel ARES ou AutoCAD n'est nécessaire : les profils utilisables sont déjà fournis en DXF dans le dépôt.

## Méthode recommandée : conserver le dépôt complet

1. Sur la page GitHub du projet, cliquer sur **Code**, puis **Download ZIP**.
2. Extraire entièrement le ZIP dans un dossier stable, qui ne sera pas déplacé après l'ajout dans Fusion.
3. Dans Fusion, ouvrir **Utilitaires > Scripts et compléments**.
4. Ouvrir l'onglet **Compléments**, cliquer sur le bouton **+**, puis sélectionner :

   ```text
   <dossier extrait>/fusion-free-structure/addin/JHR_StructuralMembers_V1
   ```

5. Sélectionner `JHR_StructuralMembers_V1` dans la liste et cliquer sur **Exécuter**.
6. Facultatif : activer **Exécuter au démarrage** pour charger automatiquement le complément lors des prochaines ouvertures de Fusion.
7. Dans l'espace **Conception**, ouvrir l'onglet **STRUCTURE JHR** et vérifier que les boutons affichent la version courante, par exemple `Profil acier V1.21.0`.

Il faut conserver le dossier `profiles` à la racine du dépôt. Le complément le recherche par un chemin relatif et doit trouver les 341 profils normalisés.

## Méthode autonome dans le dossier des compléments Windows

Cette variante permet de ne pas conserver tout le dépôt à son emplacement d'extraction.

1. Fermer ou arrêter le complément dans **Utilitaires > Scripts et compléments**.
2. Copier le dossier `addin/JHR_StructuralMembers_V1` dans :

   ```text
   %APPDATA%/Autodesk/Autodesk Fusion 360/API/AddIns/
   ```

3. Copier ensuite le dossier `profiles` de la racine du dépôt **à l'intérieur** du dossier installé :

   ```text
   %APPDATA%/Autodesk/Autodesk Fusion 360/API/AddIns/JHR_StructuralMembers_V1/profiles
   ```

4. Relancer Fusion, ou sélectionner le complément puis cliquer sur **Exécuter**.

L'arborescence autonome obtenue doit notamment contenir :

```text
JHR_StructuralMembers_V1/
├── JHR_StructuralMembers_V1.py
├── JHR_StructuralMembers_V1.manifest
├── commands/
├── lib/
├── resources/
└── profiles/
    └── Zones_geographiques/
        └── Europe/
```

## Mettre à jour le complément

1. Télécharger et extraire la nouvelle version du dépôt.
2. Dans Fusion, cliquer sur **Arrêter** pour l'ancienne version.
3. Remplacer les fichiers du complément et la bibliothèque `profiles` par ceux de la nouvelle version, en conservant l'une des deux arborescences décrites ci-dessus.
4. Cliquer sur **Exécuter**.
5. Vérifier le numéro affiché sur le bouton `Profil acier`.

Les profils personnalisés et les valeurs enregistrées par `Paramètres Structure JHR` ne sont pas stockés dans le dossier du complément. Ils restent dans `%APPDATA%\EI_JHR\fusion-free-structure` et ne doivent pas être supprimés lors d'une mise à jour.

## Premier contrôle

1. Créer ou ouvrir une conception avec l'historique paramétrique activé.
2. Créer une esquisse dans le composant racine et tracer une ligne.
3. Ouvrir `Profil acier`, choisir un profil et vérifier l'aperçu jaune.
4. Créer la barre et confirmer qu'un composant indépendant apparaît.
5. Pour le protocole complet, suivre [`TEST_PROTOCOL_FUSION.md`](TEST_PROTOCOL_FUSION.md).

## Dépannage rapide

- **Le bouton n'apparaît pas** : vérifier que le dossier sélectionné contient directement le manifeste et le fichier Python du complément, puis utiliser **Arrêter** et **Exécuter**.
- **Aucun profil n'apparaît** : vérifier l'emplacement du dossier `profiles` selon la méthode choisie.
- **L'ancien numéro de version reste visible** : arrêter puis relancer le complément, et vérifier que Fusion pointe vers le bon dossier.
- **La création est refusée** : vérifier que le document est une conception paramétrique éditable et que la ligne ou l'arc appartient au composant racine.
