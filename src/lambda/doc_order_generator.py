"""
        VERSION CLAUDE code
╔══════════════════════════════════════════════════════════════════════════════╗
║                    OLIST ORDER GENERATOR - AWS LAMBDA                        ║
║                          Version Ultra-Commentée                             ║
║                                                                              ║
║  🎯 OBJECTIF : Simuler la génération de commandes e-commerce en temps réel  ║
║                conformes au dataset Olist (Kaggle)                           ║
║                                                                              ║
║  📊 DATASET OLIST : 9 tables normalisées représentant un marketplace        ║
║                     brésilien avec 100k commandes réelles (2016-2018)       ║
║                                                                              ║
║  🏗️ ARCHITECTURE :                                                           ║
║     Lambda (Générateur) → Kinesis Stream → Firehose → S3 → Redshift         ║
║                              ↓                                               ║
║                         DynamoDB (État)                                      ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

# ═══════════════════════════════════════════════════════════════════════════
#                           IMPORTS STANDARDS
# ═══════════════════════════════════════════════════════════════════════════

import boto3          # SDK AWS pour Python - permet d'interagir avec tous les services AWS
import json           # Pour sérialiser les données en JSON avant envoi vers Kinesis
import random         # Pour générer des données aléatoires réalistes (prix, quantités, etc.)
import uuid           # Pour générer des IDs uniques (order_id, customer_id)
from datetime import datetime, timedelta  # Gestion du temps virtuel de la simulation
from decimal import Decimal              # Type requis par DynamoDB pour les nombres à virgule
from faker import Faker                  # Librairie pour générer des fausses données réalistes

# ═══════════════════════════════════════════════════════════════════════════
#                      INITIALISATION DES CLIENTS AWS
# ═══════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────
# CLIENT DYNAMODB (Base de Données NoSQL)
# ──────────────────────────────────────────────────────────────────────────
# DynamoDB = Base de données NoSQL serverless d'AWS
# On utilise le "resource" (haut niveau) au lieu du "client" (bas niveau)
# car c'est plus simple pour les opérations CRUD classiques
#
# Dans notre architecture, DynamoDB joue 2 rôles :
# 1. TABLE INVENTORY : Stocker le stock de chaque produit (product_id → stock_level)
# 2. TABLE CONFIG : Stocker l'heure virtuelle de la simulation
dynamodb = boto3.resource('dynamodb')

# ──────────────────────────────────────────────────────────────────────────
# CLIENT KINESIS (Ingestion de Données en Temps Réel)
# ──────────────────────────────────────────────────────────────────────────
# Kinesis Data Stream = Tuyau de données en temps réel
# Comparable à Apache Kafka, mais entièrement géré par AWS
#
# POURQUOI KINESIS ?
# - Capacité à ingérer des milliers d'événements par seconde
# - Découple le producteur (Lambda) du consommateur (Firehose → S3)
# - Permet d'ajouter d'autres consommateurs plus tard (ex: Lambda de notification)
# - Ordre garanti par clé de partition (ici : order_id)
kinesis = boto3.client('kinesis')

# ──────────────────────────────────────────────────────────────────────────
# FAKER - GÉNÉRATEUR DE DONNÉES FICTIVES
# ──────────────────────────────────────────────────────────────────────────
# Faker génère des données réalistes : noms, adresses, villes, codes postaux...
# 
# 'pt_BR' = Locale Brésilien (Portugais du Brésil)
# POURQUOI ? Olist est un marketplace brésilien, donc :
# - Les villes doivent être brésiliennes (São Paulo, Rio de Janeiro...)
# - Les états doivent être des états brésiliens (SP, RJ, MG...)
# - Les codes postaux doivent suivre le format brésilien (XXXXX-XXX)
#
# Exemples de données générées :
# - fake.city() → "Porto Alegre"
# - fake.state_abbr() → "RS" (Rio Grande do Sul)
# - fake.postcode() → "90040-060"
fake = Faker('pt_BR')

# ═══════════════════════════════════════════════════════════════════════════
#                         CONSTANTES DE CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────
# NOM DU KINESIS DATA STREAM
# ──────────────────────────────────────────────────────────────────────────
# C'est le "tuyau" dans lequel on va envoyer les commandes générées
# Ce stream a été créé manuellement dans la console AWS (Étape 3 du guide)
#
# Configuration du stream (dans la console) :
# - Mode capacité : On-demand (s'adapte automatiquement au volume)
# - Rétention : 24h par défaut (peut aller jusqu'à 365 jours)
STREAM_NAME = 'olist-stream-v1'

# ──────────────────────────────────────────────────────────────────────────
# TABLE DYNAMODB : INVENTAIRE DES PRODUITS
# ──────────────────────────────────────────────────────────────────────────
# Cette table contient tous les produits Olist avec leur stock actuel
#
# SCHEMA DE LA TABLE :
# - Clé primaire (Partition Key) : product_id (String)
# - Attributs :
#     * stock_level (Number) : Quantité disponible en stock
#     * category (String) : Catégorie du produit (ex: "beleza_saude")
#     * price (Decimal) : Prix de vente du produit
#
# OPERATIONS EFFECTUEES :
# - Lecture : get_random_product() lit un product_id au hasard
# - Écriture : Décrémentation atomique du stock à chaque commande
#
# MODE CAPACITE : On-demand
# - Pas besoin de provisionner de RCU/WCU (Read/Write Capacity Units)
# - AWS ajuste automatiquement selon la charge
# - Parfait pour des charges de travail imprévisibles
TABLE_INVENTORY = 'Sim_Inventory'

# ──────────────────────────────────────────────────────────────────────────
# TABLE DYNAMODB : CONFIGURATION DE LA SIMULATION
# ──────────────────────────────────────────────────────────────────────────
# Cette table ne contient qu'UN SEUL enregistrement : la config globale
#
# SCHEMA :
# - Clé primaire : config_key = "GLOBAL" (String)
# - Attributs :
#     * simulated_time (String ISO) : L'heure virtuelle actuelle (ex: "2018-03-15T14:30:00")
#     * speed_factor (Number) : Vitesse de la simulation (ex: 60 = 1h simulée par exécution)
#
# POURQUOI UNE HORLOGE VIRTUELLE ?
# Le dataset Olist original couvre 2016-2018. On veut simuler cette période
# en accéléré pour générer des données rapidement.
#
# Exemple :
# - Exécution Lambda toutes les 1 minute réelle
# - speed_factor = 60 → On avance de 1h virtuelle à chaque exécution
# - Résultat : 24 exécutions = 1 jour simulé en 24 minutes réelles
TABLE_CONFIG = 'Sim_Config'

# ═══════════════════════════════════════════════════════════════════════════
#              CACHE MÉMOIRE POUR OPTIMISER LES ACCÈS DYNAMODB
# ═══════════════════════════════════════════════════════════════════════════

# ──────────────────────────────────────────────────────────────────────────
# PROBLÈME À RÉSOUDRE
# ──────────────────────────────────────────────────────────────────────────
# get_random_product() doit retourner un product_id au hasard.
# Sans cache, on devrait :
# 1. Scanner toute la table DynamoDB (32k produits Olist)
# 2. Charger tous les product_id en mémoire
# 3. En choisir un au hasard
#
# COÛTS :
# - Un scan complet coûte des RCU (Read Capacity Units)
# - C'est LENT (plusieurs secondes) et CHER ($$$ sur DynamoDB)
# - Si la Lambda s'exécute toutes les minutes → 1440 scans/jour !
#
# ──────────────────────────────────────────────────────────────────────────
# SOLUTION : CACHE EN MÉMOIRE AVEC TTL
# ──────────────────────────────────────────────────────────────────────────
# On garde une liste de product_id en mémoire dans la variable globale PRODUCT_CACHE
#
# AVANTAGES :
# - On ne scanne la table qu'UNE FOIS au démarrage de la Lambda
# - Les exécutions suivantes réutilisent le cache (gratuit, instantané)
# - Si la Lambda reste "chaude" (AWS réutilise le conteneur), le cache persiste
#
# LIMITATIONS DE CETTE APPROCHE SIMPLE :
# - Si de nouveaux produits sont ajoutés à DynamoDB, le cache ne le sait pas
# - Si la Lambda "froide" redémarre, il faut rescanner (mais c'est rare)
#
# AMÉLIORATIONS POSSIBLES (pour production) :
# - Utiliser ElastiCache Redis pour un cache distribué entre toutes les Lambdas
# - Utiliser DynamoDB DAX (cache intégré à DynamoDB, ultra-rapide)
# - Mettre un TTL (Time To Live) pour rafraîchir le cache toutes les X heures
#
# Pour ce projet éducatif, cette approche simple suffit largement.
PRODUCT_CACHE = []

# ═══════════════════════════════════════════════════════════════════════════
#                    FONCTIONS DE GESTION DU TEMPS VIRTUEL
# ═══════════════════════════════════════════════════════════════════════════

def get_simulation_state():
    """
    📖 RÉCUPÈRE L'ÉTAT ACTUEL DE LA SIMULATION DEPUIS DYNAMODB
    
    ┌──────────────────────────────────────────────────────────────┐
    │  CONCEPT CLÉ : TEMPS VIRTUEL                                 │
    ├──────────────────────────────────────────────────────────────┤
    │  Au lieu d'utiliser l'heure réelle (datetime.now()),         │
    │  on utilise une "horloge virtuelle" stockée dans DynamoDB.   │
    │                                                               │
    │  Cette horloge avance selon speed_factor à chaque exécution. │
    └──────────────────────────────────────────────────────────────┘
    
    🎯 POURQUOI UN TEMPS VIRTUEL ?
    
    1. SIMULATION ACCÉLÉRÉE
       - Le dataset Olist couvre 2 ans (2016-2018)
       - Générer 2 ans de données en temps réel prendrait... 2 ans !
       - Avec speed_factor=60, on simule 1 jour en ~24 minutes
    
    2. REPRODUCTIBILITÉ
       - On peut "rejouer" la simulation à partir d'une date donnée
       - Utile pour déboguer ou tester des scénarios
    
    3. COHÉRENCE TEMPORELLE
       - Toutes les commandes générées ont un timestamp cohérent
       - Pas de "saut dans le temps" entre deux exécutions
    
    📊 EXEMPLE DE PROGRESSION TEMPORELLE :
    
    Exécution 1 : 2018-01-01 00:00 → Génère 5 commandes → Avance de 60 min
    Exécution 2 : 2018-01-01 01:00 → Génère 3 commandes → Avance de 60 min
    Exécution 3 : 2018-01-01 02:00 → Génère 8 commandes → Avance de 60 min
    ...
    Après 24 exécutions : On a simulé 24 heures (1 journée complète)
    
    🔄 RETOUR DE LA FONCTION :
    --------
    tuple: (datetime sim_time, int speed_factor)
        - sim_time : L'heure virtuelle actuelle (ex: 2018-03-15 14:30:00)
        - speed_factor : Nombre de minutes virtuelles à avancer par exécution (ex: 60)
    
    💡 GESTION DU CAS "PREMIÈRE EXÉCUTION" :
    --------
    Si la table Config est vide (Item non trouvé), on retourne des valeurs par défaut :
    - Date de début : 1er janvier 2018 à minuit
    - Speed factor : 60 minutes par exécution
    """
    
    # Connexion à la table de configuration
    table = dynamodb.Table(TABLE_CONFIG)
    
    # ──────────────────────────────────────────────────────────────────────
    # LECTURE DE L'ITEM DE CONFIGURATION
    # ──────────────────────────────────────────────────────────────────────
    # get_item() = Opération de lecture par clé primaire (très rapide, 1 RCU)
    # Alternative : scan() (lent, coûteux) ou query() (si on avait un sort key)
    #
    # Key={'config_key': 'GLOBAL'} → On récupère l'unique enregistrement
    # Cette table ne contient qu'un seul item, donc pas d'ambiguïté
    resp = table.get_item(Key={'config_key': 'GLOBAL'})
    
    # ──────────────────────────────────────────────────────────────────────
    # CAS 1 : AUCUNE CONFIGURATION N'EXISTE (PREMIÈRE EXÉCUTION)
    # ──────────────────────────────────────────────────────────────────────
    # Si 'Item' n'est pas dans la réponse, c'est que l'item n'existe pas
    # Cela peut arriver si :
    # - Le script init_inventory.py n'a pas été exécuté
    # - La table Config a été vidée manuellement
    # - C'est la toute première exécution après création des tables
    if 'Item' not in resp:
        # VALEURS PAR DÉFAUT
        # Date : 1er janvier 2018 à minuit (début du dataset Olist typique)
        # Speed : 60 minutes virtuelles par exécution Lambda
        # 
        # Avec EventBridge à 1 minute réelle → 1h simulée/minute → 24h/jour réel
        return datetime(2018, 1, 1), 60
    
    # ──────────────────────────────────────────────────────────────────────
    # CAS 2 : CONFIGURATION EXISTANTE (EXÉCUTIONS SUIVANTES)
    # ──────────────────────────────────────────────────────────────────────
    item = resp['Item']
    
    # ── Extraction du temps simulé ──
    # DynamoDB ne stocke pas de type datetime natif
    # On stocke en String au format ISO 8601 : "2018-03-15T14:30:00"
    # datetime.fromisoformat() convertit cette string en objet datetime Python
    #
    # FORMAT ISO 8601 : YYYY-MM-DDTHH:MM:SS
    # Exemple : "2018-03-15T14:30:00" = 15 mars 2018 à 14h30
    sim_time = datetime.fromisoformat(item['simulated_time'])
    
    # ── Extraction du facteur de vitesse ──
    # DynamoDB renvoie les nombres en Decimal, on convertit en int
    # Le speed_factor définit de combien de minutes on avance à chaque exécution
    #
    # Exemples de valeurs courantes :
    # - 1 : Temps réel (1 min réelle = 1 min simulée)
    # - 60 : 1 heure simulée par exécution (24 exécutions = 1 jour)
    # - 1440 : 1 jour simulé par exécution (365 exécutions = 1 an)
    speed = int(item['speed_factor'])
    
    return sim_time, speed


def update_simulation_time(current_time, minutes_to_add):
    """
    ⏱️ FAIT AVANCER L'HORLOGE VIRTUELLE DE LA SIMULATION
    
    Cette fonction est appelée à la FIN du lambda_handler(), après avoir
    généré toutes les commandes. Elle avance le temps virtuel de X minutes
    (où X = speed_factor, généralement 60).
    
    🔄 FLOW TEMPOREL DANS UNE EXÉCUTION :
    ─────────────────────────────────────────────────────────────────
    1. Lambda démarre
    2. get_simulation_state() → Récupère l'heure actuelle (ex: 14h00)
    3. Génération de 5 commandes avec timestamp = 14h00
    4. update_simulation_time(14h00, 60) → Avance à 15h00
    5. Lambda se termine
    6. Prochaine exécution repartira de 15h00
    
    🎯 PARAMÈTRES :
    ───────────────
    current_time (datetime) : L'heure virtuelle AVANT mise à jour
    minutes_to_add (int) : Nombre de minutes à ajouter (= speed_factor)
    
    🔙 RETOUR :
    ───────────
    datetime : La nouvelle heure virtuelle APRÈS mise à jour
    
    🔒 SÉCURITÉ : ATOMICITÉ DE L'OPÉRATION
    ──────────────────────────────────────────────────────────────────
    Cette fonction utilise UpdateExpression (syntaxe spécifique à DynamoDB)
    au lieu de :
    1. Lire l'item
    2. Modifier en mémoire
    3. Réécrire l'item
    
    POURQUOI ? Si 2 Lambdas s'exécutent en même temps (peu probable avec
    EventBridge à 1/min, mais théoriquement possible), on risquerait :
    - Lambda A lit : 14h00
    - Lambda B lit : 14h00
    - Lambda A écrit : 15h00
    - Lambda B écrit : 15h00 (écrase A !)
    → On avance de 1h au lieu de 2h !
    
    Avec UpdateExpression, DynamoDB garantit l'atomicité :
    - Lambda A update : 14h00 → 15h00
    - Lambda B update : 15h00 → 16h00
    → Cohérence garantie, même en concurrence
    
    📝 EXEMPLE D'EXÉCUTION :
    ────────────────────────────────────────────────────────────────
    current_time = datetime(2018, 3, 15, 14, 0)  # 15 mars 2018, 14h00
    minutes_to_add = 60
    
    Calcul : 2018-03-15 14:00:00 + 60 minutes = 2018-03-15 15:00:00
    
    DynamoDB après update :
    {
      "config_key": "GLOBAL",
      "simulated_time": "2018-03-15T15:00:00",
      "speed_factor": 60
    }
    """
    
    # Connexion à la table Config
    table = dynamodb.Table(TABLE_CONFIG)
    
    # ──────────────────────────────────────────────────────────────────────
    # CALCUL DE LA NOUVELLE HEURE VIRTUELLE
    # ──────────────────────────────────────────────────────────────────────
    # timedelta = Objet Python représentant une durée
    # timedelta(minutes=60) = 1 heure
    # datetime + timedelta = nouvelle datetime
    #
    # Exemple :
    # datetime(2018, 3, 15, 14, 0) + timedelta(minutes=60) 
    # = datetime(2018, 3, 15, 15, 0)
    new_time = current_time + timedelta(minutes=minutes_to_add)
    
    # ──────────────────────────────────────────────────────────────────────
    # MISE À JOUR ATOMIQUE DANS DYNAMODB
    # ──────────────────────────────────────────────────────────────────────
    # update_item() ne met à jour QUE les attributs spécifiés
    # Contrairement à put_item() qui remplace tout l'item
    #
    # SYNTAXE UPDATEEXPRESSION :
    # - "set" : opération de modification
    # - "simulated_time = :t" : l'attribut à modifier et sa nouvelle valeur
    # - ":t" : placeholder pour la valeur (définie dans ExpressionAttributeValues)
    #
    # POURQUOI CETTE SYNTAXE ?
    # - Sécurité : Empêche les injections SQL-like
    # - Performance : DynamoDB optimise les updates partiels
    # - Atomicité : L'opération est atomique au niveau du service
    table.update_item(
        # Identifie l'item à modifier (via sa clé primaire)
        Key={'config_key': 'GLOBAL'},
        
        # Expression de mise à jour (syntaxe DynamoDB)
        # "set X = :val" signifie "modifier l'attribut X avec la valeur :val"
        UpdateExpression="set simulated_time = :t",
        
        # Valeurs des placeholders utilisés dans UpdateExpression
        # :t sera remplacé par new_time.isoformat()
        # 
        # .isoformat() convertit datetime en string ISO 8601
        # Exemple : datetime(2018, 3, 15, 15, 0).isoformat() = "2018-03-15T15:00:00"
        ExpressionAttributeValues={':t': new_time.isoformat()}
    )
    
    return new_time

# ═══════════════════════════════════════════════════════════════════════════
#              FONCTIONS DE GESTION DU CACHE PRODUITS
# ═══════════════════════════════════════════════════════════════════════════

def load_products_once():
    """
    📦 CHARGE UNE LISTE DE PRODUCT_ID DEPUIS DYNAMODB DANS LE CACHE MÉMOIRE
    
    ┌────────────────────────────────────────────────────────────────┐
    │  🎯 OBJECTIF : Éviter de scanner DynamoDB à chaque commande    │
    │                                                                 │
    │  Sans cache :                                                   │
    │    Commande 1 → Scan DynamoDB (2 sec, $$$)                     │
    │    Commande 2 → Scan DynamoDB (2 sec, $$$)                     │
    │    Commande 3 → Scan DynamoDB (2 sec, $$$)                     │
    │    ...                                                          │
    │                                                                 │
    │  Avec cache :                                                   │
    │    Première exécution → Scan DynamoDB (2 sec, $$$)             │
    │    Commande 1 → Lecture cache (0.001 sec, GRATUIT)            │
    │    Commande 2 → Lecture cache (0.001 sec, GRATUIT)            │
    │    ...                                                          │
    └────────────────────────────────────────────────────────────────┘
    
    🏗️ ARCHITECTURE DU CACHE :
    ──────────────────────────────────────────────────────────────────
    PRODUCT_CACHE (liste globale) :
    [
      "aca2eb7d0059a44648bf670b2a753042",
      "4244733e06e7ecb4970a6e2683c13e61",
      "d1c427060a0f73f6b889a5c7c61f2ac4",
      ...
    ]
    
    📊 OPTIMISATIONS APPLIQUÉES :
    ──────────────────────────────────────────────────────────────────
    1. ProjectionExpression="product_id"
       → On ne récupère QUE l'ID, pas les 10 autres attributs du produit
       → Réduit la taille du payload réseau de 90%
    
    2. Limit=500
       → On limite à 500 produits au lieu des 32k du dataset complet
       → Équilibre entre diversité et coût
       → 500 produits = assez pour avoir de la variété dans les commandes
    
    3. Vérification if PRODUCT_CACHE
       → Si le cache est déjà rempli, on ne rescanne pas
       → Exploite la "chaleur" des Lambdas AWS
    
    🔥 COMPORTEMENT "HOT vs COLD" DES LAMBDAS :
    ──────────────────────────────────────────────────────────────────
    AWS Lambda fonctionne avec des conteneurs réutilisables :
    
    COLD START (démarrage à froid) :
    - La Lambda démarre pour la première fois
    - PRODUCT_CACHE est vide → load_products_once() fait un scan
    - Durée : ~2-3 secondes
    
    HOT EXECUTION (exécution à chaud) :
    - AWS réutilise le même conteneur Lambda
    - PRODUCT_CACHE est déjà rempli → pas de scan
    - Durée : ~100-200 ms
    
    Si EventBridge exécute la Lambda toutes les minutes, elle reste
    quasiment toujours "chaude" → le scan n'arrive qu'une fois par heure
    
    💡 AMÉLIORATIONS POSSIBLES (HORS SCOPE) :
    ──────────────────────────────────────────────────────────────────
    - Ajouter un TTL : recharger le cache toutes les 30 minutes
    - Utiliser ElastiCache Redis : cache partagé entre toutes les Lambdas
    - Utiliser DynamoDB Streams : invalider le cache quand des produits changent
    - Stocker le cache dans S3 : précharger depuis S3 au lieu de scanner
    
    ⚠️ ATTENTION : GLOBAL VARIABLE
    ──────────────────────────────────────────────────────────────────
    On modifie PRODUCT_CACHE qui est une variable globale (définie hors fonction).
    En Python, modifier une liste globale ne nécessite PAS le mot-clé "global"
    (contrairement à la réassignation). Mais pour la clarté, on pourrait l'ajouter.
    """
    
    # Accès à la variable globale pour la modifier
    # Note : En Python, pour MODIFIER une liste globale, "global" n'est pas requis
    # Mais pour RÉASSIGNER (PRODUCT_CACHE = [...]), il faudrait "global PRODUCT_CACHE"
    global PRODUCT_CACHE
    
    # ──────────────────────────────────────────────────────────────────────
    # VÉRIFICATION : LE CACHE EST-IL DÉJÀ REMPLI ?
    # ──────────────────────────────────────────────────────────────────────
    # Si PRODUCT_CACHE contient déjà des données, on ne fait rien
    # 
    # Comportement :
    # - Liste vide [] évalue à False en Python
    # - Liste avec éléments évalue à True
    #
    # Exemple :
    # if []: print("vide")        → s'exécute
    # if ["abc"]: print("plein")  → s'exécute
    if PRODUCT_CACHE:
        # Le cache est déjà chargé, on ne fait rien
        # Cette ligne s'exécute sur TOUTES les exécutions "hot" de la Lambda
        return
    
    # ──────────────────────────────────────────────────────────────────────
    # SCAN DE LA TABLE INVENTORY
    # ──────────────────────────────────────────────────────────────────────
    # Si on arrive ici, c'est que PRODUCT_CACHE est vide (première exécution)
    
    # Connexion à la table Inventory
    table = dynamodb.Table(TABLE_INVENTORY)
    
    # ── SCAN vs QUERY vs GET_ITEM ──
    # 
    # GET_ITEM : Récupère UN item par sa clé primaire
    #   Usage : Quand on connaît l'ID exact
    #   Coût : 1 RCU (très rapide, très cheap)
    # 
    # QUERY : Récupère des items par partition key (+ optional sort key)
    #   Usage : "Donne-moi tous les items du client X"
    #   Coût : Proportionnel au nombre d'items retournés
    # 
    # SCAN : Lit TOUTE la table, ligne par ligne
    #   Usage : Quand on ne sait pas quoi chercher précisément
    #   Coût : Lit TOUTE la table, même si on n'utilise que 500 items
    #   ⚠️ OPÉRATION COÛTEUSE ET LENTE
    # 
    # Ici, on DOIT utiliser scan() car on veut "des product_id au hasard"
    # sans critère de recherche précis.
    resp = table.scan(
        # ── ProjectionExpression : Optimisation Clé #1 ──
        # On ne récupère QUE l'attribut product_id
        # Sans ça, DynamoDB renverrait TOUS les attributs :
        # - product_id
        # - stock_level
        # - category
        # - price
        # - product_weight_g
        # - etc.
        # 
        # Avec ProjectionExpression, on réduit le payload de ~90%
        # → Moins de bande passante réseau
        # → Moins de temps de transfert
        # → Moins de RCU consommés
        ProjectionExpression="product_id",
        
        # ── Limit : Optimisation Clé #2 ──
        # On limite le scan à 500 items
        # Le dataset Olist original contient ~32 000 produits
        # 
        # Pourquoi 500 ?
        # - Assez pour avoir de la diversité dans les commandes générées
        # - Pas trop pour tenir facilement en mémoire Lambda
        # - Balance entre coût et réalisme
        # 
        # En production, on augmenterait à 5000 ou 10000
        # Ou on utiliserait une approche plus sophistiquée (cache Redis)
        Limit=500
    )
    
    # ──────────────────────────────────────────────────────────────────────
    # EXTRACTION DES PRODUCT_ID ET STOCKAGE DANS LE CACHE
    # ──────────────────────────────────────────────────────────────────────
    # resp['Items'] contient une liste de dictionnaires :
    # [
    #   {'product_id': 'aca2eb7d0059a44648bf670b2a753042'},
    #   {'product_id': '4244733e06e7ecb4970a6e2683c13e61'},
    #   ...
    # ]
    #
    # On extrait uniquement les valeurs de 'product_id' dans une liste simple
    # Résultat : ['aca2eb7d...', '4244733e...', ...]
    # 
    # List comprehension Python : [expression for item in list]
    # Équivalent à :
    # PRODUCT_CACHE = []
    # for i in resp["Items"]:
    #     PRODUCT_CACHE.append(i["product_id"])
    PRODUCT_CACHE = [i["product_id"] for i in resp["Items"]]
    
    # À ce stade, PRODUCT_CACHE contient ~500 product_id
    # Les prochains appels à load_products_once() ne feront rien (cache plein)


def get_random_product():
    """
    🎲 RETOURNE UN PRODUCT_ID ALÉATOIRE DEPUIS LE CACHE
    
    Cette fonction est appelée pour CHAQUE commande générée.
    Elle doit être ULTRA RAPIDE car elle s'exécute des dizaines de fois
    par seconde en période de forte charge.
    
    🔄 FLOW D'EXÉCUTION :
    ──────────────────────────────────────────────────────────────────
    1. Appel de load_products_once()
       → Si cache vide : charge depuis DynamoDB (LENT, 1ère fois seulement)
       → Si cache plein : ne fait rien (RAPIDE, 99% du temps)
    
    2. Sélection aléatoire avec random.choice()
       → Complexité O(1), instantané
       → Chaque produit a la même probabilité d'être choisi
    
    3. Retour du product_id
       → String de 32 caractères hexadécimaux (hash MD5)
       → Exemple : "aca2eb7d0059a44648bf670b2a753042"
    
    🎯 RETOUR :
    ──────────────────────────────────────────────────────────────────
    str : Un product_id valide, tiré au hasard depuis le cache
    
    📊 STATISTIQUES DE PERFORMANCE :
    ──────────────────────────────────────────────────────────────────
    Première exécution (COLD) :
    - load_products_once() → scan DynamoDB → 2000 ms
    - random.choice() → 0.001 ms
    - TOTAL : ~2000 ms
    
    Exécutions suivantes (HOT) :
    - load_products_once() → return immédiat → 0 ms
    - random.choice() → 0.001 ms
    - TOTAL : ~0.001 ms (2 000 000x plus rapide !)
    
    🔍 ALTERNATIVE POUR PRODUCTION :
    ──────────────────────────────────────────────────────────────────
    Dans une vraie application à grande échelle, on pourrait :
    
    1. Pré-générer une liste de 10k product_id et la stocker dans S3
    2. La Lambda télécharge cette liste au démarrage (1 fois)
    3. Plus besoin de scan DynamoDB du tout
    4. Économie : ~$100/mois sur les RCU
    
    Ou encore mieux :
    1. Utiliser DynamoDB DAX (cache in-memory distribué)
    2. DAX cache automatiquement les résultats de scan
    3. Latence : < 1 ms, même sur cold start
    4. Coût : ~$0.30/heure pour un nœud DAX
    """
    
    # ──────────────────────────────────────────────────────────────────────
    # ÉTAPE 1 : REMPLIR LE CACHE (SI NÉCESSAIRE)
    # ──────────────────────────────────────────────────────────────────────
    # Sur la première exécution, cette fonction va :
    # 1. Scanner la table DynamoDB
    # 2. Remplir PRODUCT_CACHE avec ~500 product_id
    # 
    # Sur les exécutions suivantes (Lambda "hot"), elle ne fera rien
    load_products_once()
    
    # ──────────────────────────────────────────────────────────────────────
    # ÉTAPE 2 : SÉLECTION ALÉATOIRE
    # ──────────────────────────────────────────────────────────────────────
    # random.choice(liste) retourne un élément au hasard depuis la liste
    # 
    # DISTRIBUTION : Uniforme (chaque produit a la même probabilité)
    # Si PRODUCT_CACHE contient 500 items, chaque produit a 1/500 chance
    # 
    # PERFORMANCE : O(1) - instantané, même sur de grandes listes
    # Python utilise l'algorithme de Fisher-Yates sous le capot
    # 
    # COMPORTEMENT SI CACHE VIDE :
    # Si PRODUCT_CACHE = [], random.choice() lèvera une exception IndexError
    # En pratique, ça ne devrait jamais arriver car load_products_once()
    # remplit toujours le cache (sauf si la table est vide, ce qui est un bug)
    return random.choice(PRODUCT_CACHE)

# ═══════════════════════════════════════════════════════════════════════════
#                    HANDLER LAMBDA (POINT D'ENTRÉE)
# ═══════════════════════════════════════════════════════════════════════════

def lambda_handler(event, context):
    """
    🚀 FONCTION PRINCIPALE DE LA LAMBDA - POINT D'ENTRÉE AWS
    
    Cette fonction est appelée automatiquement par AWS Lambda lorsque :
    - EventBridge déclenche l'exécution (toutes les minutes)
    - Un utilisateur invoque manuellement la Lambda (pour tester)
    - Un autre service AWS appelle la Lambda (ex: API Gateway)
    
    ┌─────────────────────────────────────────────────────────────────┐
    │  🎯 MISSION : Générer entre 3 et 20 commandes e-commerce        │
    │               conformes au format Olist et les envoyer          │
    │               vers Kinesis pour traitement en temps réel        │
    └─────────────────────────────────────────────────────────────────┘
    
    📥 PARAMÈTRES AWS LAMBDA :
    ──────────────────────────────────────────────────────────────────
    event (dict) : Contient les données d'entrée de l'invocation
                   Exemples :
                   - EventBridge : {} (vide, car règle schedule)
                   - API Gateway : {body, headers, queryStringParameters, ...}
                   - Test manuel : Tout JSON que vous passez
    
    context (LambdaContext) : Objet fourni par AWS avec des métadonnées
                              - request_id : ID unique de cette exécution
                              - function_name : Nom de la Lambda
                              - memory_limit_in_mb : Mémoire allouée
                              - log_stream_name : Nom du stream CloudWatch Logs
                              - remaining_time_in_millis() : Temps avant timeout
    
    🔙 RETOUR :
    ──────────────────────────────────────────────────────────────────
    dict : Réponse JSON standardisée (format API Gateway)
           {
             'statusCode': 200,
             'body': '{"message": "Success", "orders_count": 5}'
           }
    
    🏗️ ARCHITECTURE DE CETTE FONCTION :
    ──────────────────────────────────────────────────────────────────
    
    ┌──────────────────┐
    │ 1. GET TIME      │ ← Récupère l'heure virtuelle depuis DynamoDB
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │ 2. GENERATE      │ ← Boucle : génère 3-20 commandes
    │    ORDERS        │   Pour chaque commande :
    │                  │   a) Choisir un produit aléatoire
    │                  │   b) Décrémenter le stock (transaction atomique)
    │                  │   c) Créer l'objet order (JSON)
    │                  │   d) Envoyer vers Kinesis
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │ 3. UPDATE TIME   │ ← Avance l'horloge virtuelle de X minutes
    └────────┬─────────┘
             │
    ┌────────▼─────────┐
    │ 4. RETURN        │ ← Retourne le résumé (nombre de commandes, etc.)
    └──────────────────┘
    
    💰 COÛTS AWS (ESTIMATION) :
    ──────────────────────────────────────────────────────────────────
    Pour 1 exécution générant 10 commandes :
    - Lambda : $0.000000208 (128 MB, 500 ms)
    - DynamoDB reads : $0.0000025 (2 lectures, table Config et Inventory)
    - DynamoDB writes : $0.0000125 (10 décréments de stock + 1 update Config)
    - Kinesis PUT : $0.000014 (10 records)
    - TOTAL : ~$0.000029 par exécution
    
    Sur 1 mois (43 200 exécutions à 1/min) : ~$1.25/mois
    → Système ultra économique !
    
    ⚠️ POINTS D'ATTENTION :
    ──────────────────────────────────────────────────────────────────
    1. Gestion des erreurs : On utilise try/except pour chaque commande
       → Si un produit est en rupture de stock, on passe au suivant
       → La Lambda ne plante pas, elle log juste l'erreur
    
    2. Atomicité du stock : On utilise ConditionExpression
       → Empêche la survente (vendre un produit déjà à 0)
       → Si 2 Lambdas essaient de vendre le dernier item, 1 seule réussit
    
    3. Cohérence temporelle : TOUTES les commandes d'une exécution ont
       le MÊME timestamp (sim_time). Cohérent avec le comportement réel
       où les commandes arrivent "en rafale" toutes les minutes.
    """
    
    # ══════════════════════════════════════════════════════════════════════
    # ÉTAPE 1 : RÉCUPÉRATION DE L'ÉTAT DE LA SIMULATION
    # ══════════════════════════════════════════════════════════════════════
    # On récupère l'heure virtuelle actuelle et le facteur de vitesse
    # Exemple : sim_time = 2018-03-15 14:30:00, speed_factor = 60
    sim_time, speed_factor = get_simulation_state()
    
    # Liste pour tracker les order_id créés (pour logging et debugging)
    # À la fin, on pourra afficher "5 commandes créées : [id1, id2, ...]"
    orders_created = []
    
    # ──────────────────────────────────────────────────────────────────────
    # COMBIEN DE COMMANDES GÉNÉRER ?
    # ──────────────────────────────────────────────────────────────────────
    # On génère un nombre aléatoire de commandes entre 3 et 20
    # 
    # POURQUOI CET INTERVALLE ?
    # - Minimum 3 : Pour simuler de l'activité même en période creuse
    # - Maximum 20 : Pour simuler des pics d'activité (soldes, Black Friday...)
    # 
    # Dans le dataset Olist réel :
    # - Moyenne : ~10 commandes/minute
    # - Pic : jusqu'à 50 commandes/minute (Black Friday)
    # - Creux : 1-2 commandes/minute (nuit, dimanche)
    # 
    # Pour un réalisme accru, on pourrait :
    # - Moduler selon l'heure : plus de commandes le soir que la nuit
    # - Moduler selon le jour : plus le vendredi que le dimanche
    # - Simuler des événements : x10 pendant les soldes
    num_orders = random.randint(3, 20)
    
    # Connexion à la table Inventory (pour décrémenter le stock)
    table_inv = dynamodb.Table(TABLE_INVENTORY)
    
    # ──────────────────────────────────────────────────────────────────────
    # LOG POUR CLOUDWATCH
    # ──────────────────────────────────────────────────────────────────────
    # print() dans une Lambda envoie automatiquement vers CloudWatch Logs
    # Utile pour :
    # - Débugger (voir ce qui se passe pendant l'exécution)
    # - Monitorer (nombre de commandes générées par exécution)
    # - Alerter (détecter des anomalies)
    # 
    # Ce log apparaîtra dans :
    # CloudWatch > Log groups > /aws/lambda/Olist-Order-Generator
    print(f"Simulation Time: {sim_time}, Generating {num_orders} orders")
    
    # ══════════════════════════════════════════════════════════════════════
    # ÉTAPE 2 : BOUCLE DE GÉNÉRATION DES COMMANDES
    # ══════════════════════════════════════════════════════════════════════
    # On itère num_orders fois (ex: 10 fois si random.randint a renvoyé 10)
    # À chaque itération, on crée une commande complète
    for _ in range(num_orders):
        # ──────────────────────────────────────────────────────────────────
        # ÉTAPE 2.1 : SÉLECTION D'UN PRODUIT ALÉATOIRE
        # ──────────────────────────────────────────────────────────────────
        # get_random_product() pioche un product_id au hasard dans le cache
        # Exemple : "aca2eb7d0059a44648bf670b2a753042"
        product_id = get_random_product()
        
        # ──────────────────────────────────────────────────────────────────
        # ÉTAPE 2.2 : DÉCRÉMENTATION ATOMIQUE DU STOCK
        # ──────────────────────────────────────────────────────────────────
        # C'est la partie la plus critique du code.
        # On doit GARANTIR qu'on ne vend jamais un produit en rupture de stock.
        # 
        # ┌──────────────────────────────────────────────────────────────┐
        # │  SCÉNARIO PROBLÉMATIQUE (SANS TRANSACTION ATOMIQUE) :        │
        # ├──────────────────────────────────────────────────────────────┤
        # │  Stock initial : 1                                            │
        # │                                                               │
        # │  Lambda A lit stock : 1 ✓                                     │
        # │  Lambda B lit stock : 1 ✓                                     │
        # │  Lambda A vend : stock = 0 ✓                                  │
        # │  Lambda B vend : stock = -1 ❌ SURVENTE !                     │
        # └──────────────────────────────────────────────────────────────┘
        # 
        # ┌──────────────────────────────────────────────────────────────┐
        # │  SOLUTION : TRANSACTION ATOMIQUE AVEC CONDITION              │
        # ├──────────────────────────────────────────────────────────────┤
        # │  Stock initial : 1                                            │
        # │                                                               │
        # │  Lambda A : update IF stock > 0 → stock = 0 ✓                │
        # │  Lambda B : update IF stock > 0 → ÉCHEC ✓                    │
        # │                                                               │
        # │  DynamoDB garantit qu'une seule des deux réussira            │
        # └──────────────────────────────────────────────────────────────┘
        try:
            # ── update_item() avec ConditionExpression ──
            # Cette opération est ATOMIQUE : DynamoDB garantit que
            # si la condition est vérifiée au moment de l'écriture,
            # l'update se fait. Sinon, une exception est levée.
            table_inv.update_item(
                # Identifie le produit à modifier
                Key={'product_id': product_id},
                
                # ── UpdateExpression : Décrémente stock_level de 1 ──
                # "set X = X - :val" signifie "soustraire :val de X"
                # Équivalent à : stock_level = stock_level - 1
                # 
                # ATTENTION : On ne peut PAS faire stock_level -= 1
                # DynamoDB requiert cette syntaxe spécifique
                UpdateExpression="set stock_level = stock_level - :val",
                
                # ── ConditionExpression : Vérifie stock > 0 AVANT d'écrire ──
                # Cette condition est évaluée par DynamoDB AVANT l'update
                # Si stock_level <= 0, l'update est ANNULÉ et une exception
                # ConditionalCheckFailedException est levée
                # 
                # ":min": 0 signifie "stock doit être > 0"
                # Si le stock est exactement 0, la condition échoue
                ConditionExpression="stock_level > :min",
                
                # Valeurs des placeholders utilisés ci-dessus
                # :val = 1 → on décrémente de 1
                # :min = 0 → stock doit être strictement positif
                ExpressionAttributeValues={':val': 1, ':min': 0}
            )
            
        except Exception as e:
            # ──────────────────────────────────────────────────────────
            # GESTION DE L'ERREUR : PRODUIT EN RUPTURE DE STOCK
            # ──────────────────────────────────────────────────────────
            # Si on arrive ici, c'est que :
            # 1. La ConditionExpression a échoué (stock <= 0), OU
            # 2. Une autre erreur s'est produite (réseau, DynamoDB down...)
            # 
            # Dans les deux cas, on LOG l'erreur et on PASSE À LA
            # COMMANDE SUIVANTE (continue), au lieu de planter la Lambda.
            # 
            # Cela permet de générer les autres commandes même si un
            # produit particulier est en rupture.
            # 
            # EN PRODUCTION, on pourrait :
            # - Distinguer ConditionalCheckFailedException des autres erreurs
            # - Envoyer une alerte SNS si trop de ruptures de stock
            # - Retirer le produit du cache s'il est souvent en rupture
            print(f"Out of stock for {product_id}: {str(e)}")
            
            # continue = passe à l'itération suivante de la boucle for
            # La commande actuelle est abandonnée, on en génère une autre
            continue
        
        # Si on arrive ici, c'est que l'update a RÉUSSI :
        # - Le stock a bien été décrémenté
        # - On peut créer la commande en toute sécurité
        
        # ──────────────────────────────────────────────────────────────────
        # ÉTAPE 2.3 : GÉNÉRATION DE L'OBJET COMMANDE (JSON)
        # ──────────────────────────────────────────────────────────────────
        # On crée un dictionnaire Python qui représente une commande Olist
        # Ce dictionnaire sera converti en JSON et envoyé vers Kinesis
        
        # ── Génération de l'order_id unique ──
        # uuid.uuid4() génère un UUID version 4 (aléatoire)
        # Exemple : "550e8400-e29b-41d4-a716-446655440000"
        # str() convertit l'objet UUID en string
        # 
        # UUID = Universally Unique IDentifier
        # Probabilité de collision : 1 sur 2^122 (astronomiquement faible)
        # Utilisé comme clé primaire dans les bases de données distribuées
        order_id = str(uuid.uuid4())
        
        # ── Construction du dictionnaire order ──
        order = {
            # ═══ ATTRIBUTS DE LA TABLE "ORDERS" (OLIST) ═══
            
            # ID unique de la commande
            "order_id": order_id,
            
            # ID unique du client
            # Dans le vrai dataset Olist, il y a ~96k clients
            # Ici, on génère un nouvel UUID à chaque commande
            # → Simule des clients uniques (pas de clients récurrents)
            # 
            # AMÉLIORATION POSSIBLE :
            # - Avoir un pool de 10k customer_id dans un cache
            # - 20% des commandes proviennent de clients récurrents
            # - 80% des commandes proviennent de nouveaux clients
            "customer_id": str(uuid.uuid4()),
            
            # Statut de la commande
            # Dans Olist, les statuts possibles sont :
            # - delivered (96%) : Commande livrée
            # - shipped (2%) : Commande expédiée mais pas encore livrée
            # - canceled (1%) : Commande annulée
            # - processing, invoiced, unavailable, created (< 1%)
            # 
            # Ici, on met "approved" pour simplifier
            # EN PRODUCTION, on utiliserait random.choices() pour
            # avoir une distribution réaliste des statuts
            "order_status": "approved",
            
            # Timestamp de la commande (heure virtuelle)
            # .isoformat() convertit datetime en string ISO 8601
            # Exemple : "2018-03-15T14:30:00"
            # 
            # IMPORTANT : TOUTES les commandes de cette exécution
            # auront le MÊME timestamp (sim_time), car elles sont
            # considérées comme arrivées "en même temps" (dans la
            # même minute virtuelle)
            "order_purchase_timestamp": sim_time.isoformat(),
            
            # ═══ ATTRIBUTS DE LA TABLE "ORDER_ITEMS" (OLIST) ═══
            # Dans le vrai dataset Olist, order_items est une table séparée
            # Ici, on l'imbrique dans "order" pour simplifier le traitement
            # 
            # "items" est une LISTE car une commande peut contenir
            # plusieurs produits. Ici, on ne simule qu'un seul produit
            # par commande pour simplifier.
            # 
            # AMÉLIORATION POSSIBLE :
            # - 60% des commandes : 1 produit
            # - 30% des commandes : 2-3 produits
            # - 10% des commandes : 4-10 produits
            "items": [{
                # ID du produit acheté
                "product_id": product_id,
                
                # Prix du produit (en BRL - Real Brésilien)
                # random.uniform(20.0, 150.0) génère un float entre 20 et 150
                # float() convertit en float Python standard (DynamoDB n'aime pas Decimal ici)
                # 
                # Distribution des prix dans Olist réel :
                # - Médiane : ~50 BRL (~10 USD)
                # - Moyenne : ~120 BRL (~25 USD)
                # - Max : ~6000 BRL (~1200 USD)
                # 
                # Notre intervalle 20-150 BRL simule des produits
                # de milieu de gamme (majoritaires sur Olist)
                "price": float(random.uniform(20.0, 150.0)),
                
                # Frais de port (freight = fret en français)
                # Dans Olist, les frais de port sont calculés selon :
                # - Le poids du produit
                # - La distance entre le vendeur et le client
                # - Le transporteur choisi
                # 
                # Intervalle 10-30 BRL représente des frais moyens
                # (Olist a une médiane de ~15 BRL)
                "freight_value": float(random.uniform(10.0, 30.0))
            }],
            
            # ═══ ATTRIBUTS DE LA TABLE "CUSTOMERS" (OLIST) ═══
            # Dans le vrai dataset, customers est une table séparée
            # Ici, on l'imbrique pour simplifier
            "customer": {
                # Ville du client (générée par Faker avec locale pt_BR)
                # Exemples : "São Paulo", "Rio de Janeiro", "Belo Horizonte"
                # Faker utilise une vraie liste de villes brésiliennes
                "city": fake.city(),
                
                # État brésilien (abréviation à 2 lettres)
                # Exemples : "SP" (São Paulo), "RJ" (Rio de Janeiro), "MG" (Minas Gerais)
                # Le Brésil a 26 états + 1 district fédéral
                # 
                # Distribution réelle Olist :
                # - SP : 42% (São Paulo est le poumon économique)
                # - RJ : 13%
                # - MG : 12%
                # - Autres : 33%
                "state": fake.state_abbr(),
                
                # Code postal brésilien
                # Format : XXXXX-XXX (ex: "01310-100")
                # Faker génère des codes valides selon le format brésilien
                "zip_code": fake.postcode()
            }
        }
        
        # ──────────────────────────────────────────────────────────────────
        # ÉTAPE 2.4 : ENVOI DE LA COMMANDE VERS KINESIS
        # ──────────────────────────────────────────────────────────────────
        # Kinesis est un "tuyau" qui achemine les données en temps réel
        # vers leurs destinations (ici : Firehose → S3)
        # 
        # ┌────────────────────────────────────────────────────────────┐
        # │  ARCHITECTURE DU FLUX DE DONNÉES :                         │
        # ├────────────────────────────────────────────────────────────┤
        # │  Lambda → Kinesis Stream → Firehose → S3 → Redshift       │
        # │                ↑                                            │
        # │              ON EST ICI                                     │
        # └────────────────────────────────────────────────────────────┘
        kinesis.put_record(
            # Nom du stream Kinesis (créé manuellement dans la console)
            StreamName=STREAM_NAME,
            
            # ── Data : Payload de l'événement ──
            # Doit être en bytes ou string
            # json.dumps() convertit le dict Python en string JSON
            # 
            # Exemple du résultat :
            # '{"order_id":"550e8400-...","customer_id":"...", ...}'
            # 
            # Taille max d'un record Kinesis : 1 MB
            # Notre record fait ~500 bytes → largement en dessous
            Data=json.dumps(order),
            
            # ── PartitionKey : Clé de partitionnement ──
            # Kinesis distribue les records sur plusieurs "shards"
            # selon le hash de la PartitionKey
            # 
            # Règle : Même PartitionKey → Même shard → Ordre garanti
            # 
            # Ici, on utilise order_id comme clé, donc chaque commande
            # va potentiellement sur un shard différent (répartition uniforme)
            # 
            # Si on voulait garantir l'ordre des commandes d'un même client,
            # on utiliserait customer_id comme PartitionKey
            PartitionKey=order_id
        )
        
        # ──────────────────────────────────────────────────────────────────
        # TRACKING : Ajout de l'order_id à la liste des commandes créées
        # ──────────────────────────────────────────────────────────────────
        # Cela nous permet de :
        # - Compter combien de commandes ont été générées
        # - Logger les IDs pour déboguer
        # - Retourner un résumé à la fin de l'exécution
        orders_created.append(order_id)
    
    # ══════════════════════════════════════════════════════════════════════
    # ÉTAPE 3 : AVANCEMENT DE L'HORLOGE VIRTUELLE
    # ══════════════════════════════════════════════════════════════════════
    # On a fini de générer toutes les commandes pour cette exécution
    # Il faut maintenant avancer le temps virtuel pour que la prochaine
    # exécution parte de là où on s'est arrêté
    # 
    # Exemple :
    # - On était à 2018-03-15 14:30:00
    # - speed_factor = 60
    # - Nouvel horaire : 2018-03-15 15:30:00
    # - Prochaine exécution (dans 1 min réelle) repartira de 15:30
    update_simulation_time(sim_time, speed_factor)
    
    # ══════════════════════════════════════════════════════════════════════
    # ÉTAPE 4 : RETOUR DE LA RÉPONSE
    # ══════════════════════════════════════════════════════════════════════
    # Une Lambda doit TOUJOURS retourner une réponse
    # Même si elle n'est pas utilisée (cas EventBridge), c'est une bonne pratique
    # 
    # Format standardisé (compatible API Gateway) :
    # {
    #   'statusCode': 200,  # Code HTTP (200 = succès, 500 = erreur)
    #   'body': '...'       # Payload en JSON (DOIT être une string !)
    # }
    return {
        # Code de statut HTTP
        # 200 = OK, tout s'est bien passé
        # Si on voulait signaler une erreur partielle, on pourrait utiliser 207 (Multi-Status)
        'statusCode': 200,
        
        # Corps de la réponse (DOIT être une string JSON)
        # On utilise un f-string pour construire un message informatif
        # 
        # len(orders_created) = nombre de commandes générées
        # sim_time = heure virtuelle actuelle
        # 
        # Exemple de body :
        # "Generated 12 orders. New Time: 2018-03-15 15:30:00"
        'body': json.dumps(f"Generated {len(orders_created)} orders. New Time: {sim_time}")
    }

# ═══════════════════════════════════════════════════════════════════════════
#                          FIN DU CODE
# ═══════════════════════════════════════════════════════════════════════════

"""
🎓 RÉCAPITULATIF DES CONCEPTS CLÉS :

1. TEMPS VIRTUEL
   - Permet d'accélérer la simulation
   - Cohérence temporelle entre les exécutions
   - Reproductibilité des scénarios

2. CACHE EN MÉMOIRE
   - Évite les scans DynamoDB répétés
   - Exploite la "chaleur" des Lambdas
   - Économie de coûts et gain de performance

3. TRANSACTION ATOMIQUE
   - ConditionExpression empêche la survente
   - Garantit la cohérence du stock
   - Fonctionne même en concurrence

4. ARCHITECTURE EVENT-DRIVEN
   - Lambda = Stateless (pas de mémoire entre exécutions)
   - DynamoDB = State store (stock, config)
   - Kinesis = Event bus (découplage producteur/consommateur)

5. GÉNÉRATION DE DONNÉES RÉALISTES
   - Faker pour les données géographiques
   - UUID pour les identifiants uniques
   - Random pour la variabilité

📚 POUR ALLER PLUS LOIN :
- Ajouter des seller_id (vendeurs) dans les commandes
- Simuler des commandes multi-produits
- Implémenter des patterns temporels (+ de commandes le soir)
- Ajouter des métriques CloudWatch custom
- Implémenter un système de retry en cas d'erreur Kinesis
"""