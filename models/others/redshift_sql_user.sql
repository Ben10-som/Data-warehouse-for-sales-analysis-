CREATE USER bi_analyst WITH PASSWORD 'PASSword78945@#$%&';

-- Autoriser l'utilisateur à se connecter à la base de données
GRANT CONNECT ON DATABASE dev TO bi_analyst;

-- Autoriser l'utilisateur à voir le schéma externe créé
GRANT USAGE ON SCHEMA olist_spectrum_schema TO bi_analyst;

-- Autoriser la sélection sur la table Parquet
GRANT SELECT ON olist_spectrum_schema.table_order_sim TO bi_analyst;