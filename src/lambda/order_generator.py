import boto3
import json
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from faker import Faker



dynamodb = boto3.resource('dynamodb')
kinesis = boto3.client('kinesis')
fake = Faker('pt_BR') # On utilise le locale Brésilien pour Olist !

# Constants
STREAM_NAME = 'olist-stream-v1'
TABLE_INVENTORY = 'Sim_Inventory'
TABLE_CONFIG = 'Sim_Config'

def get_simulation_state():
    """Récupère l'heure virtuelle actuelle"""
    table = dynamodb.Table(TABLE_CONFIG)
    resp = table.get_item(Key={'config_key': 'GLOBAL'})
    # Si pas de config, on met une valeur par défaut
    if 'Item' not in resp:
        return datetime(2018, 1, 1), 60
        
    item = resp['Item']
    sim_time = datetime.fromisoformat(item['simulated_time'])
    speed = int(item['speed_factor'])
    return sim_time, speed

def update_simulation_time(current_time, minutes_to_add):
    """Met à jour l'heure virtuelle"""
    table = dynamodb.Table(TABLE_CONFIG)
    new_time = current_time + timedelta(minutes=minutes_to_add)
    table.update_item(
        Key={'config_key': 'GLOBAL'},
        UpdateExpression="set simulated_time = :t",
        ExpressionAttributeValues={':t': new_time.isoformat()}
    )
    return new_time

# Cache mémoire pour stocker temporairement les IDs produits
# Objectif : éviter de scanner toute la table DynamoDB à chaque appel (coûteux et lent).
PRODUCT_CACHE = []

def load_products_once():
    """
    Charge une liste limitée d'IDs produits depuis DynamoDB
    et les met en cache dans PRODUCT_CACHE.
    - Utilise un scan avec ProjectionExpression pour ne récupérer que la clé 'product_id'
    - Limite volontairement à 500 items pour réduire le coût et la latence
    """
    global PRODUCT_CACHE
    # Si le cache est déjà rempli, on ne recharge pas
    if PRODUCT_CACHE:
        return

    # Connexion à la table inventaire
    table = dynamodb.Table(TABLE_INVENTORY)
    resp = table.scan(
        ProjectionExpression="product_id",  # On ne récupère que l'ID produit
        Limit=500                           
    )
    # On extrait uniquement les IDs et on les stocke en mémoire
    PRODUCT_CACHE = [i["product_id"] for i in resp["Items"]]

def get_random_product():
    """
    Retourne un produit aléatoire parmi ceux présents dans le cache.
    Astuce :
    - Dans un vrai projet, on aurait un cache plus robuste (Redis, DAX, etc.)
    - Ici, pour simplifier, on recharge une fois et on pioche au hasard
    - Cela évite de faire un scan complet de la table à chaque commande
    """
    # remplir le cache
    load_products_once()
    # Sélection aléatoire d'un product_id
    return random.choice(PRODUCT_CACHE)

def lambda_handler(event, context):
    sim_time, speed_factor = get_simulation_state()
    orders_created = []
    
    # On génère entre 3 et 20 commandes par execution
    num_orders = random.randint(3, 20)
    
    table_inv = dynamodb.Table(TABLE_INVENTORY)
    
    print(f"Simulation Time: {sim_time}, Generating {num_orders} orders")

    for _ in range(num_orders):
        product_id = get_random_product()
        
        # 1. TRANSACTION ATOMIQUE (Décrémenter Stock)
        try:
            table_inv.update_item(
                Key={'product_id': product_id},
                UpdateExpression="set stock_level = stock_level - :val",
                ConditionExpression="stock_level > :min",
                ExpressionAttributeValues={':val': 1, ':min': 0}
            )
        except Exception as e:
            print(f"Out of stock for {product_id}: {str(e)}")
            continue # Skip order

        # 2. Création de la donnée (Format Olist enrichi)
        order_id = str(uuid.uuid4())
        order = {
            "order_id": order_id,
            "customer_id": str(uuid.uuid4()),
            "order_status": "approved",
            "order_purchase_timestamp": sim_time.strftime("%Y-%m-%d %H:%M:%S"),
            "items": [{
                "product_id": product_id,
                "price": float(random.uniform(20.0, 150.0)),
                "freight_value": float(random.uniform(10.0, 30.0))
            }],
            "customer": {
                "city": fake.city(),
                "state": fake.state_abbr(),
                "zip_code": fake.postcode()
            }
        }
        
        # 3. Envoi vers Kinesis
        kinesis.put_record(
            StreamName=STREAM_NAME,
            Data=json.dumps(order),
            PartitionKey=order_id
        )
        orders_created.append(order_id)

    # On avance de X minutes, où X = nombre de commandes générées × speed_factor
    minutes_to_add = len(orders_created) * speed_factor
    new_sim_time = update_simulation_time(sim_time, minutes_to_add)
    
    return {
    'statusCode': 200,
    'body': json.dumps({
        'message': f"Generated {len(orders_created)} orders",
        'orders_generated': len(orders_created),
        'previous_time': sim_time.isoformat(),
        'new_time': new_sim_time.isoformat(),
        'minutes_advanced': minutes_to_add
    })
}