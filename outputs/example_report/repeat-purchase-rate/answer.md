# How many customers placed more than one order, how many placed exactly one, and what percentage of customers are repeat buyers?

Out of your customer base, 30 customers placed more than one order, while only 2 placed exactly one order. This means repeat buyers make up 93.75% of your customers, indicating a very strong retention rate and a customer base that overwhelmingly returns for additional purchases.

## Query

```sql
WITH order_counts AS (
    SELECT customer_id, COUNT(*) AS order_count
    FROM orders
    GROUP BY customer_id
)
SELECT
    SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) AS repeat_customers,
    SUM(CASE WHEN order_count = 1 THEN 1 ELSE 0 END) AS single_order_customers,
    ROUND(100.0 * SUM(CASE WHEN order_count > 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS repeat_customer_percentage
FROM order_counts
LIMIT 100
```

## Result

| repeat_customers | single_order_customers | repeat_customer_percentage |
| --- | --- | --- |
| 30 | 2 | 93.75 |

---
_Generated 2026-08-07 00:47:54 · 1 row(s) · approved by a human before execution._
