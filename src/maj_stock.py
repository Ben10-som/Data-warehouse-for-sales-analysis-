import boto3
import random

"""
Script exécuté en local pour recharger le stock des produits dans DynamoDB.

Principe :
- Scan complet de la table Sim_Inventory :obligatoire !
- Pour chaque produit, on ajoute une quantité aléatoire au stock
- Tous les produits ne sont pas forcément rechargés (probabilité)
"""

dynamodb = boto3.resource("dynamodb")
TABLE_NAME = "Sim_Inventory"


def replenish_inventory(
    min_add: int = 50,
    max_add: int = 300,
    probability: float = 0.9
):
    """
    Ajoute aléatoirement du stock aux produits existants dans la table DynamoDB.
    """

    if not (0 <= probability <= 1):
        raise ValueError("probability doit être comprise entre 0 et 1")

    table = dynamodb.Table(TABLE_NAME)

    print(f"Début du rechargement du stock : {TABLE_NAME}")
    print(
        f"Ajout entre {min_add} et {max_add} unités "
        f"(probabilité {probability * 100:.1f} %)"
    )

    total_updated = 0

    scan_kwargs = {
        "ProjectionExpression": "product_id, stock_level"
    }

    response = table.scan(**scan_kwargs)

    while True:
        items = response.get("Items", [])

        for item in items:
            product_id = item["product_id"]

            if random.random() > probability:
                continue

            add_amount = random.randint(min_add, max_add)

            table.update_item(
                Key={"product_id": product_id},
                UpdateExpression="ADD stock_level :inc",
                ExpressionAttributeValues={":inc": add_amount}
            )

            total_updated += 1

            if total_updated % 100 == 0:
                print(f"{total_updated} produits rechargés (dernier : {product_id} +{add_amount})")

        if "LastEvaluatedKey" in response:
            response = table.scan(
                ExclusiveStartKey=response["LastEvaluatedKey"],
                **scan_kwargs
            )
        else:
            break

    print(f"Rechargement terminé : {total_updated} produits mis à jour.")


if __name__ == "__main__":
    replenish_inventory(
        min_add=200,
        max_add=850,
        probability=0.91
    )
