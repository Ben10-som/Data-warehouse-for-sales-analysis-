        ########################################################################################
        # À chaque exécution, la fonction génère un nombre aléatoire de commandes,
        # mais chacune ne contient qu’un seul produit.
        #
        # Techniquement, il serait possible d’ajouter plusieurs produits par commande
        # en alimentant la liste `items`. Cependant, cela oblige à changer la consommation
        # côté AWS Firehose, qui considère par défaut une seule table cible.
        #
        # Dans ce cas, il faudrait adapter :
        #   - le schéma externe Glue,
        #   - la transformation Silver dans dbt,
        #   - et les paramètres de livraison Firehose (par ex. activer le partitionnement dynamique pour alimenter plusieurs dossiers S3).
        #
        # En pratique, cette évolution permettrait de transformer notre projet
        # en un véritable jumeau numérique temps réel, avec plusieurs consommateurs
        # branchés sur le même Kinesis Data Stream.
                #
        # Dans un vrai site comme Olist, DynamoDB est un bon choix car :
        #   - On ne fait pas de scan complet, mais des requêtes ciblées
        #     grâce aux clés primaires et aux index globaux secondaires (GSI).
        #   - Les accès sont optimisés pour récupérer directement un produit,
        #     un client ou une commande sans parcourir toute la table.
        #   - DynamoDB supporte des millions de requêtes par seconde
        #     avec une latence très faible, idéal pour un e-commerce.
        #   - Il s’intègre nativement avec Kinesis, Lambda, Glue et même Redshift avec Dynamodb Stream,
        #     ce qui simplifie la mise en place d’un pipeline temps réel.
        #
        # Notre choix de DynamoDB est donc justifié :
        #   - il sert de socle transactionnel fiable,
        #   - il est hautement disponible et résilient,
        #   - et il permet de prototyper rapidement un jumeau numérique qui ressemble au vrai site web
        #
        # Les scans qu’on utilise ici sont juste une simplification
        # pour la simulation. Dans la vraie vie, Olist utiliserait
        # des requêtes indexées et du caching (Redis/DAX) pour éviter
        # toute surcharge et garantir la performance.
        ########################################################################################




# speed_factor = 60 signifie desormais :le délai entre deux commandes peut aller jusqu’à 60 minutes environ

import boto3
import json
import random
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
import math

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
    # horloge virtuelle progressive (on la fait avancer commande par commande)
    current_virtual_time = sim_time
    total_advanced_seconds = 0.0

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


        #  attribution d'un timestamp unique et réaliste pour chaque commande
        # offset aléatoire borné par speed_factor 
        offset_seconds = random.uniform(0, max(1, speed_factor) * 60)  
        # jitter de 0..59 secondes pour éviter des timestamps trop "propres"
        jitter_seconds = random.uniform(0, 59)
        increment = timedelta(seconds=offset_seconds + jitter_seconds)

        # avancer l'horloge virtuelle progressive
        current_virtual_time = current_virtual_time + increment
        total_advanced_seconds += (offset_seconds + jitter_seconds)

        # 2. Création de la donnée (Format Olist enrichi)
        order_id = str(uuid.uuid4())
        order = {
            "order_id": order_id,
            "customer_id": str(uuid.uuid4()),
            "order_status": "approved",
            "order_purchase_timestamp": current_virtual_time.strftime("%Y-%m-%d %H:%M:%S"),
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

    # Convertir la somme des secondes avancées en minutes 
    minutes_to_add = math.ceil(total_advanced_seconds / 60) if total_advanced_seconds > 0 else 0
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