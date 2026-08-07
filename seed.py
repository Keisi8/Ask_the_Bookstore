"""Build bookstore.db from the CSV files in data/.

Idempotent: drops and recreates every table, so you can re-run it any time.
    python seed.py
"""

import csv
import sqlite3
from pathlib import Path

ROOT = Path(__file__).parent
DATA = ROOT / "data"
DB_PATH = ROOT / "bookstore.db"

SCHEMA = """
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS books;

CREATE TABLE books (
    book_id        INTEGER PRIMARY KEY,
    title          TEXT    NOT NULL,
    author         TEXT    NOT NULL,
    genre          TEXT    NOT NULL,
    price          REAL    NOT NULL,  -- current list price in EUR
    published_year INTEGER NOT NULL
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    city        TEXT NOT NULL,
    signup_date TEXT NOT NULL         -- ISO date, YYYY-MM-DD
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date  TEXT    NOT NULL,     -- ISO date, YYYY-MM-DD
    channel     TEXT    NOT NULL      -- 'web' | 'in-store' | 'phone'
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    book_id       INTEGER NOT NULL REFERENCES books(book_id),
    quantity      INTEGER NOT NULL,
    unit_price    REAL    NOT NULL    -- price actually paid, may be discounted
);
"""

# table -> (csv file, column order, per-column cast)
TABLES = {
    "books": ("books.csv",
              ["book_id", "title", "author", "genre", "price", "published_year"],
              {"book_id": int, "price": float, "published_year": int}),
    "customers": ("customers.csv",
                  ["customer_id", "name", "city", "signup_date"],
                  {"customer_id": int}),
    "orders": ("orders.csv",
               ["order_id", "customer_id", "order_date", "channel"],
               {"order_id": int, "customer_id": int}),
    "order_items": ("order_items.csv",
                    ["order_item_id", "order_id", "book_id", "quantity", "unit_price"],
                    {"order_item_id": int, "order_id": int, "book_id": int,
                     "quantity": int, "unit_price": float}),
}


def load(conn: sqlite3.Connection, table: str) -> int:
    filename, columns, casts = TABLES[table]
    with (DATA / filename).open(newline="", encoding="utf-8") as f:
        rows = [
            tuple(casts.get(c, str)(row[c]) for c in columns)
            for row in csv.DictReader(f)
        ]
    placeholders = ", ".join("?" * len(columns))
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", rows
    )
    return len(rows)


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    for table in TABLES:
        print(f"  {table:<12} {load(conn, table):>4} rows")
    conn.commit()
    conn.close()
    print(f"\nWrote {DB_PATH}")


if __name__ == "__main__":
    main()
