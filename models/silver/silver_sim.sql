{{ config(materialized='table') }}

-- Nous retirons la CTE 'base_data' et allons directement à l'éclatement.

WITH unpivot_items AS (
    SELECT
        t.order_id,
        t.customer_id,
        t.order_purchase_timestamp,
        -- Eclatement du tableau 'items'. 'item' est l'alias de l'objet JSON individuel.
        item.product_id AS product_id,
        item.price AS price,
        item.freight_value AS freight_value,
        t.customer  -- Sélection de l'objet client pour la prochaine extraction
    FROM
        -- Référence directe à la source Spectrum avec un alias 't'
        {{ source('olist_spectrum_schema', 'table_order_sim') }} AS t,
        -- Dé-nichage du tableau SUPER en utilisant l'alias 't'
        t.items AS item
    WHERE
        t.order_status = 'approved' -- La condition WHERE est appliquée ici
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