{{ config(materialized='table') }}

WITH base_data AS (
    SELECT
        order_id,
        customer_id,
        order_status,
        order_purchase_timestamp,
        items,      -- Colonne de type SUPER (tableau de JSON)
        customer    -- Colonne de type SUPER (objet JSON)
    FROM
        {{ source('olist_spectrum_schema', 'table_order_sim') }}
    WHERE
        order_status = 'approved'
),

unpivot_items AS (
    SELECT
        order_id,
        customer_id,
        order_purchase_timestamp,
        -- Eclatement du tableau 'items'. 'item' est l'alias de l'objet JSON individuel.
        item.product_id AS product_id,
        item.price AS price,
        item.freight_value AS freight_value,
        customer
    FROM
        base_data,
        base_data.items AS item -- Dé-nichage du tableau SUPER
)

SELECT
    order_id,
    customer_id,
    order_purchase_timestamp,
    product_id,
    (price + freight_value) AS total_price,
    -- Extraction des champs de l'objet 'customer' avec la notation par point
    customer.city AS customer_city,
    customer.state AS customer_state
FROM
    unpivot_items