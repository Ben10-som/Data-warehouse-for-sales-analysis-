CREATE USER bi_analyst WITH PASSWORD 'PASSword78945@#$%&';

-- Autoriser l'utilisateur à se connecter à la base de données
GRANT CONNECT ON DATABASE dev TO bi_analyst;

-- Autoriser l'utilisateur à voir le schéma externe créé
GRANT USAGE ON SCHEMA olist_spectrum_schema TO bi_analyst;


-- Donner accès en lecture seule à la table
GRANT SELECT ON ALL TABLES IN SCHEMA olist_spectrum_schema TO bi_analyst;

ALTER DEFAULT PRIVILEGES IN SCHEMA olist_spectrum_schema
GRANT SELECT ON TABLES TO bi_analyst;
