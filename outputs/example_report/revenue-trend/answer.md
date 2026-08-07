# What is the total revenue for each month, ordered chronologically? Show the month as YYYY-MM and the revenue rounded to 2 decimals.

Revenue starts low at $20.70 in February 2024, then climbs through the year, peaking at $777.37 in November 2024 before dropping to $250.19 in December 2024. From January 2025 onward, revenue stabilizes in a higher range, generally between $396 and $561, with September 2025 at $561.25 being the highest shown. Note that only 20 of the 23 total months are displayed here, so the most recent months' figures aren't visible in this summary.

## Query

```sql
SELECT strftime('%Y-%m', o.order_date) AS month,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY month
ORDER BY month
LIMIT 100
```

## Result

| month | total_revenue |
| --- | --- |
| 2024-02 | 20.7 |
| 2024-03 | 278.89 |
| 2024-04 | 369.47 |
| 2024-05 | 159.5 |
| 2024-06 | 26.1 |
| 2024-07 | 138.0 |
| 2024-08 | 273.71 |
| 2024-09 | 271.89 |
| 2024-10 | 367.95 |
| 2024-11 | 777.37 |
| 2024-12 | 250.19 |
| 2025-01 | 452.51 |
| 2025-02 | 453.18 |
| 2025-03 | 419.72 |
| 2025-04 | 396.35 |
| 2025-05 | 466.08 |
| 2025-06 | 400.77 |
| 2025-07 | 413.07 |
| 2025-08 | 441.35 |
| 2025-09 | 561.25 |
| _... 3 more rows in result.csv_ | |

---
_Generated 2026-08-07 00:46:42 · 23 row(s) · approved by a human before execution._
