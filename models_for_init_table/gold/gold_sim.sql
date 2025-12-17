{{ config(materialized='table') }}

SELECT
    DATE_TRUNC('day', order_purchase_timestamp) AS order_date,
    customer_state,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(total_price) AS daily_revenue
FROM
    {{ ref('silver_sim') }} -- Référence au modèle Silver créé juste avant
GROUP BY 1, 2
ORDER BY 1, 2