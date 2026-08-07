SELECT o.channel,
       COUNT(DISTINCT o.order_id) AS order_count,
       ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.channel
LIMIT 100
