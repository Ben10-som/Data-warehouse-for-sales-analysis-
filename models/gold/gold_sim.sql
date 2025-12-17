{{ config(
    materialized='incremental',
    unique_key='order_date'
) }}

SELECT
    DATE_TRUNC('day', order_purchase_timestamp) AS order_date,
    customer_state,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(total_price) AS daily_revenue
FROM
    {{ ref('silver_sim') }}
    
{% if is_incremental() %}
  -- On ne recalcule que les jours présents dans les nouvelles données de silver_sim
  WHERE DATE_TRUNC('day', order_purchase_timestamp) >= (select max(order_date) from {{ this }})
{% endif %}

GROUP BY 1, 2