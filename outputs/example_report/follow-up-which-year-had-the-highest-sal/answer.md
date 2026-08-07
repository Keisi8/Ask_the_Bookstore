# Which year had the highest sales in the genre Science Fiction?

2025 had the highest sales for Science Fiction, generating $1,424.72 in total revenue, the top year among those recorded.

## Query

```sql
SELECT strftime('%Y', o.order_date) AS year,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN books b ON oi.book_id = b.book_id
WHERE b.genre LIKE '%Science%'
GROUP BY year
ORDER BY total_revenue DESC
LIMIT 1
```

## Result

| year | total_revenue |
| --- | --- |
| 2025 | 1424.72 |

---
_Generated 2026-08-07 00:58:51 · 1 row(s) · approved by a human before execution._
