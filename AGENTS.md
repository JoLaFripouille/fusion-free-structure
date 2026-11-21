# Structure JHR dans Fusion

Pour le choix des outils natifs, les commandes JHR et le MCP, lire [le guide Fusion et MCP](docs/FUSION-MCP.md).

Pour modéliser un profil acier dans Fusion, rechercher la section dans `list_profiles` et appeler `create_members` ou `create_columns` via le mode script du MCP. Utiliser le DXF de référence avec ses congés. Pour une section absente du catalogue, utiliser un DXF vérifié avant de lancer la création.

Avant de créer une pièce qui dépend de la verticale, relever le sens de la hauteur sur le modèle cible. Les dessins en Y vertical ont le sol dans XZ. Les dessins en Z vertical ont le sol dans XY.
