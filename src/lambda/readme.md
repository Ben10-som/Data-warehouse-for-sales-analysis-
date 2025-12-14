# Fonction order_generator :

## Cache des produits DynamoDB

Ce module gère un petit cache mémoire des `product_id` afin d'éviter de scanner toute la table DynamoDB à chaque appel.  
Cela permet de réduire la latence et le coût des requêtes.

### Fonctionnalités

### `load_products_once()`
Charge une liste limitée d'IDs produits depuis la table **Sim_Inventory** et les stocke dans une variable globale `PRODUCT_CACHE`.

- Utilise `ProjectionExpression="product_id"` pour ne récupérer que la clé primaire.
- Limite volontairement à **500 items** pour réduire le coût et la latence.
- Ne recharge pas si le cache est déjà rempli.