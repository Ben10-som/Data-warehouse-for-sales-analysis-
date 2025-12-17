{{ config(
    materialized='incremental',
    unique_key='order_id'
) }}

WITH unpivot_items AS (
    SELECT
        t.order_id,
        t.customer_id,
        t.order_purchase_timestamp,
        item.product_id AS product_id,
        item.price AS price,
        item.freight_value AS freight_value,
        t.customer
    FROM
        {{ source('olist_spectrum_schema', 'table_order_sim') }} AS t,
        t.items AS item
    WHERE
        t.order_status = 'approved'
        
    {% if is_incremental() %}
      -- Filtre : On ne prend que ce qui est plus récent que la date max déjà en table
      AND t.order_purchase_timestamp > (select max(order_purchase_timestamp) from {{ this }})
    {% endif %}
)

SELECT
    order_id,
    customer_id,
    order_purchase_timestamp,
    product_id,
    (price + freight_value) AS total_price,
    TRIM(customer.city::VARCHAR, '"') AS customer_city,
    TRIM(customer.state::VARCHAR, '"') AS customer_state
FROM
    unpivot_items