SELECT strftime('%Y', o.order_date) AS year,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN books b ON oi.book_id = b.book_id
WHERE b.genre LIKE '%Science%'
GROUP BY year
ORDER BY total_revenue DESC
LIMIT 1
