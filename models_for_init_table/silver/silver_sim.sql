{{ config(materialized='table') }}

WITH unpivot_items AS (
    SELECT
        t.order_id,
        t.customer_id,
        t.order_purchase_timestamp,
        item.product_id AS product_id,
        item.price AS price,
        item.freight_value AS freight_value,
        t.customer  -- L'objet customer struct
    FROM
        {{ source('olist_spectrum_schema', 'table_order_sim') }} AS t,
        t.items AS item
    WHERE
        t.order_status = 'approved'
)

SELECT
    order_id,
    customer_id,
    order_purchase_timestamp,
    product_id,
    (price + freight_value) AS total_price,
    -- CORRECTION : Caster le résultat de l'extraction SUPER en VARCHAR avant d'utiliser TRIM
    TRIM(customer.city::VARCHAR, '"') AS customer_city,
    TRIM(customer.state::VARCHAR, '"') AS customer_state
FROM
    unpivot_items