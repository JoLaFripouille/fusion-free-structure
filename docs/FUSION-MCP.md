# Guide Fusion et MCP

## Repère du dessin

Dans les dessins en **Y vers le haut**, les poteaux montent suivant **Y** et le sol est dans **XZ**. Dans les dessins en **Z vers le haut**, le sol est dans **XY**. Avant une opération qui dépend de la hauteur, contrôler le repère sur une pièce verticale connue ou sur une face de sol. La préférence donne un indice et l'orientation de la vue peut varier.

Pour modifier la préférence générale, ouvrir **Avatar → Préférences → Général → Orientation de modélisation par défaut**, choisir **Z vers le haut** ou **Y vers le haut**, puis redémarrer Fusion. Pour un modèle existant, vérifier la géométrie réelle. [Référence Autodesk](https://help.autodesk.com/cloudhelp/ENU/Fusion-GetStarted/files/GUID-878489CD-3A23-4303-8450-C2F4F8E410B1.htm)

## Entrées disponibles

Le MCP Autodesk Fusion donne accès à la session ouverte. Découvrir les schémas actifs de `fusion_mcp_read` et `fusion_mcp_execute`. Identifier d'abord le document, son état et la commande active. Pour une inspection par script utiliser `featureType="script"` et `readOnly=true`. L'API Design exprime les longueurs en centimètres et les angles en radians. Les opérations Structure JHR documentent leurs arguments en millimètres ou degrés dans la signature.

Les commandes visibles de **Structure JHR** utilisent le même code que les entrées de [`mcp_operations.py`](../addin/JHR_StructuralMembers_V1/lib/mcp_operations.py), invoquées depuis le mode script du MCP.

| Besoin | Commande Fusion ou entrée script JHR |
|---|---|
| Profils et squelette | Profil acier, Poteaux, Modifier un profil, Inspecter un profil acier, `create_members`, `replace_member_section` |
| Coupes et grugeages | Jonctions acier, Grugeage profils ouverts, `create_joint` |
| Pieds, abouts, jarrets, éclissages, goussets | Pieds de poteau, Assemblages acier, Copier un assemblage, Modifier un assemblage, Supprimer un assemblage, Inspecter un assemblage, `assembly_templates`, `create_assembly`, `inspect_assembly` |
| Pannes I/H reprises sur des poutres I/H | Raccorder les pannes |
| Cornières d'attache | Attaches de poutres par cornières, `create_double_angle` avec `opposite_token` facultatif |
| Boulons, vis et écrous à sertir | Visserie → Boulonnerie JHR, `place_bolts`, `place_tapped_screw`, `place_rivet_nut` |
| Garde-corps | Garde-corps acier, Tronçonner un garde-corps, `create_guardrail`, `segment_guardrail` |
| Bibliothèques et réglages locaux | Gérer les profils personnalisés, Paramètres Structure JHR |

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
