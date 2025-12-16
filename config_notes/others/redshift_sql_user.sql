CREATE USER bi_analyst WITH PASSWORD 'PASSword78945@#$%&';

-- Autoriser l'utilisateur à se connecter à la base de données
GRANT CONNECT ON DATABASE dev TO bi_analyst;

-- Autoriser l'utilisateur à voir le schéma externe créé
GRANT USAGE ON SCHEMA olist_spectrum_schema TO bi_analyst;


-- Donner accès en lecture seule à la table
GRANT SELECT ON ALL TABLES IN SCHEMA olist_spectrum_schema TO bi_analyst;

ALTER DEFAULT PRIVILEGES IN SCHEMA olist_spectrum_schema
GRANT SELECT ON TABLES TO bi_analyst;

-- Nouveaux droits pour Silver/Gold

GRANT USAGE ON SCHEMA dbt_sim_silver_gold TO bi_analyst;

GRANT SELECT ON ALL TABLES IN SCHEMA dbt_sim_silver_gold TO bi_analyst;

ALTER DEFAULT PRIVILEGES IN SCHEMA dbt_sim_silver_gold
GRANT SELECT ON TABLES TO bi_analyst;


-- Nouveaux droit pour silver/gold apres changement :

-- 1. Autoriser l'accès au schéma
GRANT USAGE ON SCHEMA dbt_sim_silver_gold TO bi_analyst;

-- 2. Donner les droits SELECT sur les tables actuelles (gold_sim vient d'être recréée)
GRANT SELECT ON ALL TABLES IN SCHEMA dbt_sim_silver_gold TO bi_analyst;

-- 3. Définir les droits par défaut pour que les prochains "dbt run" donnent automatiquement les droits
ALTER DEFAULT PRIVILEGES IN SCHEMA dbt_sim_silver_gold
GRANT SELECT ON TABLES TO bi_analyst;