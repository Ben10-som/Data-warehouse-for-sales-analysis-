-- silver_sim.sql
-- Transformation des données brutes vers Silver

WITH raw AS (

    SELECT *
    FROM spectrum.olist_dw-sim-catalog
)

SELECT
    CAST(order_id AS VARCHAR(50))       AS order_id,
    CAST(customer_id AS VARCHAR(50))    AS customer_id,
    CAST(product_id AS VARCHAR(50))     AS product_id,
    CAST(order_date AS DATE)            AS order_date,
    CAST(price AS DECIMAL(10,2))        AS price,
    status
FROM raw
WHERE order_id IS NOT NULL;
