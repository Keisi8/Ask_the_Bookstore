# Which 10 books sold the fewest copies overall? Show title, author, genre, total copies sold and total revenue, ordered by copies ascending. Include books that have never been ordered.

The weakest sellers are "Nightjar" (Poetry, Ines Kovac), "Root and Branch" (Nature Writing, Eleanor Fitzgibbon), and "The Silent Quarter" (Mystery, Tomas Brandt), each with just 1 copy sold and revenue between $11.50 and $21.00. Just behind them are four titles tied at 2 copies sold: "The Kepler Drift" ($34.50), "Tidelines" ($43.18), "The Glass Orchard" ($29.98), and "Numbers at Night" ($28.78). Rounding out the bottom 10 are "A Grammar of Weather" with 3 copies ($36.00), and "Quiet Machines" and "Cities Made of Debt" tied at 4 copies each ($75.96 and $101.75 respectively). None of these ten books show zero sales, meaning every title in the catalog has at least one recorded order.

## Query

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

## Result

| title | author | genre | total_copies_sold | total_revenue |
| --- | --- | --- | --- | --- |
| Nightjar | Ines Kovac | Poetry | 1 | 11.5 |
| Root and Branch | Eleanor Fitzgibbon | Nature Writing | 1 | 21.0 |
| The Silent Quarter | Tomas Brandt | Mystery | 1 | 13.5 |
| The Kepler Drift | Marcus Oyelaran | Science Fiction | 2 | 34.5 |
| Tidelines | Eleanor Fitzgibbon | Nature Writing | 2 | 43.18 |
| The Glass Orchard | Sofia Marchetti | Mystery | 2 | 29.98 |
| Numbers at Night | Rashid Al-Amin | Popular Science | 2 | 28.78 |
| A Grammar of Weather | Ines Kovac | Poetry | 3 | 36.0 |
| Quiet Machines | Marcus Oyelaran | Science Fiction | 4 | 75.96 |
| Cities Made of Debt | Henrik Solberg | History | 4 | 101.75 |

---
_Generated 2026-08-07 00:48:05 · 10 row(s) · approved by a human before execution._
