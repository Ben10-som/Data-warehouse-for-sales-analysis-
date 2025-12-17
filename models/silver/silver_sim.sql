{{ config(
    materialized='incremental',
    unique_key='order_id'
) }}

{%- set max_date = None -%}
{%- if is_incremental() -%}
    {%- set max_date_query -%}
        SELECT MAX(order_purchase_timestamp) FROM {{ this }}
    {%- endset -%}
    {%- set results = run_query(max_date_query) -%}
    {%- if execute -%}
        {%- set max_date = results.columns[0][0] -%}
    {%- endif -%}
{%- endif -%}

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
        {% if is_incremental() and max_date is not none %}
        AND t.order_purchase_timestamp > '{{ max_date }}'
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