import boto3
import csv
import random
from decimal import Decimal

CSV_FILE_PATH = '../data/products.csv'
DYNAMODB_TABLE_INVENTORY = 'Sim_Inventory'
DYNAMODB_TABLE_CONFIG = 'Sim_Config'

dynamodb = boto3.resource('dynamodb')

def create_tables_if_not_exist():
    try:
        # Vérifier si les tables existent
        table_inventory = dynamodb.Table(DYNAMODB_TABLE_INVENTORY)
        table_inventory.load()
        table_config = dynamodb.Table(DYNAMODB_TABLE_CONFIG)
        table_config.load()
        print("Tables existantes trouvées.")
    except:
        print("Création des tables DynamoDB...")
        # Créer table inventory
        dynamodb.create_table(
            TableName=DYNAMODB_TABLE_INVENTORY,
            KeySchema=[{'AttributeName': 'product_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'product_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        # Créer table config
        dynamodb.create_table(
            TableName=DYNAMODB_TABLE_CONFIG,
            KeySchema=[{'AttributeName': 'config_key', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'config_key', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        print("Tables créées. Attente de l'activation...")
        dynamodb.Table(DYNAMODB_TABLE_INVENTORY).wait_until_exists()
        dynamodb.Table(DYNAMODB_TABLE_CONFIG).wait_until_exists()
        print("Tables activées.")

table_inventory = dynamodb.Table(DYNAMODB_TABLE_INVENTORY)
table_config = dynamodb.Table(DYNAMODB_TABLE_CONFIG)

def load_inventory():
    print("Début du chargement de l'inventaire ...")
    with open(CSV_FILE_PATH, mode='r', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        
        # On utilise batch_writer pour la rapidité (écrit par paquets)
        with table_inventory.batch_writer() as batch:
            count = 0
            for row in reader:
                product_id = row['product_id']
                if product_id:
                    # On génère un stock aléatoire et un prix fictif pour l'exercice
                    item = {
                        'product_id': product_id,
                        'stock_level': random.randint(50, 800),
                        'category': row.get('product_category_name', 'unknown'),
                        # DynamoDB requiert Decimal pour les nombres flottants
                        'price': Decimal(str(round(random.uniform(10.0, 500.0), 2)))
                    }
                    batch.put_item(Item=item)
                    count += 1
                    if count % 1000 == 0:
                        print(f"{count} produits chargés...")
    print(f"TERMINÉ : {count} produits insérés dans Sim_Inventory.")

def init_config():
    print("Initialisation de la configuration temps...")
    table_config.put_item(
        Item={
            'config_key': 'GLOBAL',
            'simulated_time': '2018-01-01T00:00:00', # Date de début simulation
            'speed_factor': Decimal('60') # 1 min réelle = 1 heure simulée
        }
    )
    print("TERMINÉ : Configuration initialisée.")

if __name__ == '__main__':
    create_tables_if_not_exist()
    load_inventory()
    init_config()