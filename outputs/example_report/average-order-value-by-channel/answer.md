# What is the average order value for each sales channel? Average order value means total revenue divided by the number of distinct orders. Include the order count for each channel.

In-store orders have the highest average order value at $48.67 across 66 orders, closely followed by web orders at $48.47 across 93 orders. Phone orders lag behind with an average order value of $43.49 across just 21 orders, making it both the lowest-value and lowest-volume channel.

## Query

```sql
SELECT o.channel,
       COUNT(DISTINCT o.order_id) AS order_count,
       ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.channel
LIMIT 100
```

## Result

| channel | order_count | avg_order_value |
| --- | --- | --- |
| in-store | 66 | 48.67 |
| phone | 21 | 43.49 |
| web | 93 | 48.47 |

---
_Generated 2026-08-07 00:47:14 · 3 row(s) · approved by a human before execution._
