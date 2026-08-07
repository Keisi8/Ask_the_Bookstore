# Weekly Commercial Review

_Generated 2026-08-07_00-45-33. Every query below was reviewed and approved by a human before it ran._

## Contents

- [Revenue trend](#revenue-trend)
- [Average order value by channel](#average-order-value-by-channel)
- [Top titles by revenue](#top-titles-by-revenue)
- [Repeat purchase rate](#repeat-purchase-rate)
- [Slow movers](#slow-movers)

## Revenue trend

**Question:** What is the total revenue for each month, ordered chronologically? Show the month as YYYY-MM and the revenue rounded to 2 decimals.

Revenue starts low at $20.70 in February 2024, then climbs through the year, peaking at $777.37 in November 2024 before dropping to $250.19 in December 2024. From January 2025 onward, revenue stabilizes in a higher range, generally between $396 and $561, with September 2025 at $561.25 being the highest shown. Note that only 20 of the 23 total months are displayed here, so the most recent months' figures aren't visible in this summary.

<details><summary>Query that ran</summary>

```sql
SELECT strftime('%Y-%m', o.order_date) AS month,
       ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
FROM orders o
JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY month
ORDER BY month
LIMIT 100
```

</details>

## Average order value by channel

**Question:** What is the average order value for each sales channel? Average order value means total revenue divided by the number of distinct orders. Include the order count for each channel.

In-store orders have the highest average order value at $48.67 across 66 orders, closely followed by web orders at $48.47 across 93 orders. Phone orders lag behind with an average order value of $43.49 across just 21 orders, making it both the lowest-value and lowest-volume channel.

<details><summary>Query that ran</summary>

```sql
SELECT o.channel,
       COUNT(DISTINCT o.order_id) AS order_count,
       ROUND(SUM(oi.quantity * oi.unit_price) / COUNT(DISTINCT o.order_id), 2) AS avg_order_value
FROM orders o
JOIN order_items oi ON oi.order_id = o.order_id
GROUP BY o.channel
LIMIT 100
```

</details>

## Top titles by revenue

**Question:** Which 10 books generated the most revenue, and what share of total revenue does each represent as a percentage?

The top-performing book is "Kitchen Latin" with $773.80 in revenue, representing 8.96% of total revenue, followed by "The Lagrange Job" at $603.10 (6.99%) and "On Not Deciding" at $598.60 (6.93%). Rounding out the top five are "The Beekeeper's Year" at $559.70 (6.48%) and "Deep Water Signals" at $461.68 (5.35%). The remaining top 10 include "Everything Is a Wave" ($460.00, 5.33%), "Concrete Utopias" ($442.75, 5.13%), "The Understudy" ($404.25, 4.68%), "Signal Fires" ($340.80, 3.95%), and "The Slow Kitchen" ($328.25, 3.80%). Together, these 10 books account for roughly 57.6% of total revenue.

<details><summary>Query that ran</summary>

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

</details>

## Repeat purchase rate

**Question:** How many customers placed more than one order, how many placed exactly one, and what percentage of customers are repeat buyers?

Out of your customer base, 30 customers placed more than one order, while only 2 placed exactly one order. This means repeat buyers make up 93.75% of your customers, indicating a very strong retention rate and a customer base that overwhelmingly returns for additional purchases.

<details><summary>Query that ran</summary>

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

</details>

## Slow movers

**Question:** Which 10 books sold the fewest copies overall? Show title, author, genre, total copies sold and total revenue, ordered by copies ascending. Include books that have never been ordered.

The weakest sellers are "Nightjar" (Poetry, Ines Kovac), "Root and Branch" (Nature Writing, Eleanor Fitzgibbon), and "The Silent Quarter" (Mystery, Tomas Brandt), each with just 1 copy sold and revenue between $11.50 and $21.00. Just behind them are four titles tied at 2 copies sold: "The Kepler Drift" ($34.50), "Tidelines" ($43.18), "The Glass Orchard" ($29.98), and "Numbers at Night" ($28.78). Rounding out the bottom 10 are "A Grammar of Weather" with 3 copies ($36.00), and "Quiet Machines" and "Cities Made of Debt" tied at 4 copies each ($75.96 and $101.75 respectively). None of these ten books show zero sales, meaning every title in the catalog has at least one recorded order.

<details><summary>Query that ran</summary>

```sql
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
```

</details>

