# Which 10 books generated the most revenue, and what share of total revenue does each represent as a percentage?

The top-performing book is "Kitchen Latin" with $773.80 in revenue, representing 8.96% of total revenue, followed by "The Lagrange Job" at $603.10 (6.99%) and "On Not Deciding" at $598.60 (6.93%). Rounding out the top five are "The Beekeeper's Year" at $559.70 (6.48%) and "Deep Water Signals" at $461.68 (5.35%). The remaining top 10 include "Everything Is a Wave" ($460.00, 5.33%), "Concrete Utopias" ($442.75, 5.13%), "The Understudy" ($404.25, 4.68%), "Signal Fires" ($340.80, 3.95%), and "The Slow Kitchen" ($328.25, 3.80%). Together, these 10 books account for roughly 57.6% of total revenue.

## Query

```sql
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
```

## Result

| book_id | title | total_revenue | revenue_share_pct |
| --- | --- | --- | --- |
| 39 | Kitchen Latin | 773.8 | 8.96 |
| 21 | The Lagrange Job | 603.1 | 6.99 |
| 31 | On Not Deciding | 598.6 | 6.93 |
| 35 | The Beekeeper's Year | 559.7 | 6.48 |
| 4 | Deep Water Signals | 461.68 | 5.35 |
| 38 | Everything Is a Wave | 460.0 | 5.33 |
| 26 | Concrete Utopias | 442.75 | 5.13 |
| 19 | The Understudy | 404.25 | 4.68 |
| 20 | Signal Fires | 340.8 | 3.95 |
| 13 | The Slow Kitchen | 328.25 | 3.8 |

---
_Generated 2026-08-07 00:47:27 · 10 row(s) · approved by a human before execution._
