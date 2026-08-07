SELECT b.title,
       b.author,
       b.genre,
       COALESCE(SUM(oi.quantity), 0) AS total_copies_sold,
       ROUND(COALESCE(SUM(oi.quantity * oi.unit_price), 0), 2) AS total_revenue
FROM books b
LEFT JOIN order_items oi ON oi.book_id = b.book_id
GROUP BY b.book_id, b.title, b.author, b.genre
ORDER BY total_copies_sold ASC
LIMIT 10
