SELECT
    b.book_id,
    b.title,
    ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue,
    ROUND(100.0 * SUM(oi.quantity * oi.unit_price) / (
        SELECT SUM(oi2.quantity * oi2.unit_price)
        FROM order_items oi2
    ), 2) AS revenue_share_pct
FROM order_items oi
JOIN books b ON b.book_id = oi.book_id
GROUP BY b.book_id, b.title
ORDER BY total_revenue DESC
LIMIT 10
