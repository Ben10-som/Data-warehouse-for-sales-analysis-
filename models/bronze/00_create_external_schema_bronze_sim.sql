CREATE EXTERNAL SCHEMA bronze_sim
FROM DATA CATALOG
DATABASE 'olist_dw-sim-catalog'
IAM_ROLE 'arn:aws:iam::xxxxxxxxxxxxxxxxxxxx'
CREATE EXTERNAL DATABASE IF NOT EXISTS;