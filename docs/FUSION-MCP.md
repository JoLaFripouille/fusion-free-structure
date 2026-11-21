# Guide Fusion et MCP

## Repère du dessin

Dans les dessins en **Y vers le haut**, les poteaux montent suivant **Y** et le sol est dans **XZ**. Dans les dessins en **Z vers le haut**, le sol est dans **XY**. Avant une opération qui dépend de la hauteur, contrôler le repère sur une pièce verticale connue ou sur une face de sol. La préférence donne un indice et l'orientation de la vue peut varier.

Pour modifier la préférence générale, ouvrir **Avatar → Préférences → Général → Orientation de modélisation par défaut**, choisir **Z vers le haut** ou **Y vers le haut**, puis redémarrer Fusion. Pour un modèle existant, vérifier la géométrie réelle. [Référence Autodesk](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GUID-878489CD-3A23-4303-8450-C2F4F8E410B1.htm)

## Entrées disponibles

Le MCP Autodesk Fusion donne accès à la session ouverte. Découvrir les schémas actifs de `fusion_mcp_read` et `fusion_mcp_execute`. Identifier d'abord le document, son état et la commande active. Pour une inspection par script utiliser `featureType="script"` et `readOnly=true`. L'API Design exprime les longueurs en centimètres et les angles en radians. Les opérations Structure JHR documentent leurs arguments en millimètres ou degrés dans la signature.

Les opérations de [`mcp_operations.py`](../addin/JHR_StructuralMembers_V1/lib/mcp_operations.py) s’appellent avec `fusion_mcp_execute` en mode `script`. Elles réutilisent les fonctions natives de **Structure JHR**. `list_operations()` affiche les noms et les signatures disponibles dans la version chargée. `active_context()` renvoie les identifiants du dessin et les jetons de la sélection active.

Pour créer un profil, chercher sa référence avec `list_profiles`, puis la passer à `create_members` avec les jetons des lignes ou arcs du squelette. Utiliser le contour du catalogue avec ses rayons, même pour une cornière. Si la section recherchée est absente, importer un DXF vérifié dans les profils personnalisés avant de la créer.

Exemple en lecture seule pour découvrir les entrées et rechercher une cornière égale de 60 × 60 × 6 mm.

```python
import importlib
import json
import sys
from pathlib import Path

import adsk.core


def run(_context):
    app = adsk.core.Application.get()
    roots = {Path(item.folder).resolve() for item in app.scripts
             if item.name == "JHR_StructuralMembers_V1" and item.isRunning}
    packages = [module.__package__ for name, module in tuple(sys.modules.items())
                if name.endswith(".lib.addin_info") and getattr(module, "ADDIN_ROOT", None) in roots]
    if len(packages) != 1:
        raise RuntimeError("Charger une seule instance de Structure JHR dans Fusion.")
    jhr = importlib.import_module(packages[0] + ".mcp_operations")
    print(json.dumps(jhr.list_operations()))
    print(json.dumps(jhr.run_operation("list_profiles", {"family": "Cornière égale", "query": "60x60"})))
```

Appeler `active_context()` avant une opération sur le modèle et reprendre ses identifiants dans les paramètres `creation_id` et, pour un dessin enregistré, `file_id`. Lorsque l’opération accepte `preview=True`, vérifier son résultat avec `readOnly=true` avant d’appliquer. Faire passer `readOnly` à `false` uniquement pour l’écriture autorisée. L’opération ne sauvegarde pas le dessin.

| Besoin | Commande Fusion ou entrée script JHR |
|---|---|
| Profils et squelette | `list_profiles`, `create_members`, `create_columns`, `inspect_member`, `edit_member`, `replace_member_section` |
| Coupes et grugeages | `create_joint`, `create_cope` |
| Pieds, abouts, jarrets, éclissages, goussets | `assembly_templates`, `create_assembly`, `inspect_assembly`, `edit_assembly`, `copy_assembly`, `remove_assembly` |
| Pannes I/H reprises sur des poutres I/H | `connect_purlins` |
| Auto-contreventement depuis deux faces | `create_brace_bay`, `edit_assembly` |
| Cornières d'attache | Attaches de poutres par cornières, `create_double_angle` avec `opposite_token` facultatif |
| Boulons, vis et écrous à sertir | `place_bolts`, `place_tapped_screw`, `place_rivet_nut`, `attach_rivet_screw` |
| Garde-corps | Garde-corps acier, Tronçonner un garde-corps, `create_guardrail`, `segment_guardrail` |
| Bibliothèque personnelle et réglages locaux | `import_custom_profile`, `remove_custom_profile`, `get_defaults`, `set_defaults` |

Dans **Visserie → Boulon tête fraisée**, sélectionner le bord rond côté tête pour créer la fraisure à la pose. Pour plusieurs pièces empilées, renseigner les faces d’appui extérieures du montage. Dans **Vis en trou taraudé**, la case **Tête fraisée** permet de fraiser l’avant-trou ou de réutiliser une fraisure existante. La longueur d’une vis fraisée se mesure tête comprise.

Dans **Écrou à sertir RIVKLE**, sélectionner la paroi du trou et la face d’introduction pour poser l’écrou seul. Une fois la pièce à serrer dessinée, revenir à la commande et choisir **Visser dans un RIVKLE posé**. Sélectionner l’insert, puis la face extérieure de la pièce percée ou saisir son épaisseur à serrer. La longueur de vis et la rondelle sous tête sont réglables.

Le champ **Fonction du profil** distingue Barre, Poteau, Poutre et Panne de la section acier. Le rôle est modifiable dans **Modifier un profil** et visible dans **Inspecter un profil acier**. `create_members` accepte `role="BARRE"`, `"POTEAU"`, `"POUTRE"` ou `"PANNE"`. Les poteaux créés depuis des points partent du Z réel du point et montent suivant Z.

Dans **Raccorder les pannes**, sélectionner les poutres porteuses, puis les pannes. Le même plat d’âme est appliqué aux abouts perpendiculaires trouvés sur les axes des poutres I/H sélectionnées. Le formulaire affiche les tôles à créer, les grugeages nécessaires et les raccords déjà réalisés. Les grugeages créés dans ce lot sont regroupés avec leur raccord.

La face extérieure des nouvelles platines de pied coïncide avec l’extrémité choisie du squelette. Le profil est raccourci de l’épaisseur de la platine. Cet usinage appartient au groupe du pied et suit sa face d’appui lorsque l’épaisseur change.

Dans **Pieds de poteau**, les **Dimensions libres** utilisent la largeur, la longueur et le déport saisis. Les **Débords autour du poteau** utilisent les quatre distances aux faces de la section dans ses axes locaux. Chaque axe des perçages suit soit un entraxe fixe, soit la distance des axes des trous aux deux bords. Les collisions avec les goussets sont contrôlées avec le jeu choisi et, si présentes, les rondelles. Une cote incompatible est signalée en rouge dans son groupe de réglages.

Dans **Modifier → Copier un assemblage**, choisir une pièce de l’assemblage source, puis les profils cibles demandés selon le type. La copie est indépendante par défaut. Pour les pieds de poteau modifiables, l’option de liaison partage les réglages du pied. Chaque poteau conserve sa propre ébauche. **Inspecter un assemblage** se trouve aussi dans **Modifier**.

Dans **Auto-contreventement**, sélectionner une face plane intérieure sur chacun des deux poteaux I/H JHR. Les retraits se mesurent depuis le bas et le haut de chaque face. Les onglets **Géométrie**, **Platine centrale** et **Goussets** pilotent l’aperçu. Dans **Options**, cocher **Évidements arrondis de la platine centrale** pour régler leur profondeur. Pour reprendre le montage, sélectionner une de ses pièces dans **Modifier un assemblage**. Le recalcul automatique à la suite d’une modification des faces s’applique au dernier groupe replié de l’historique, avec les déplacements déjà validés.

Dans **Modifier un assemblage**, sélectionner une pièce du groupe JHR pour retrouver le montage et ses cotes. Le pied conserve sa liaison au squelette lors d’une rotation du poteau. **Supprimer un assemblage** retire le groupe d’historique sélectionné et les usinages qu’il contient. Un grugeage préparé dans un groupe séparé conserve son propre historique.

Pour les paramètres et les sélections, lire la signature de la commande ou appeler `assembly_templates()` pour les assemblages à platines. Résoudre les jetons dans le document visé et vérifier les appuis, la pose et la géométrie créée. Le réglage `vertical_axis` du garde-corps accepte `"auto"`, `"Y"` ou `"Z"`.

Le modèle `barreaude` de `create_guardrail` contrôle les vides réels des travées et sous la lisse basse. Pour tronçonner un garde-corps industriel, sélectionner un poteau plat. En rampant la main courante est coupée perpendiculairement à son axe. Les autres lisses et la plinthe suivent le plan des deux plats.
