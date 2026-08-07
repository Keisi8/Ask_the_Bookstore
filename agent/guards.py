"""Safety checks applied to LLM-generated SQL before a human ever sees it.

The human is the *last* line of defence, not the only one. These checks reject
anything that isn't a single read-only query, so the approval prompt only ever
shows the reviewer plausible SQL.

Every function here is pure: no database, no network, no API key. That makes
them trivial to unit-test -- see `python -m agent.guards` at the bottom.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_ROWS = 100

# Statement types that must never run. Word boundaries stop us matching
# 'CREATE' inside a book title like 'Concrete Utopias'.
FORBIDDEN = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE",
    "TRUNCATE", "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX", "GRANT",
)
FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN) + r")\b", re.IGNORECASE)

FENCE_RE = re.compile(r"^\s*```(?:sql)?\s*|\s*```\s*$", re.IGNORECASE)
LIMIT_RE = re.compile(r"\blimit\s+\d+", re.IGNORECASE)
STRING_LITERAL_RE = re.compile(r"'[^']*'")
LINE_COMMENT_RE = re.compile(r"--[^\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


@dataclass
class Verdict:
    """Result of validating a candidate query."""
    ok: bool
    sql: str = ""       # cleaned SQL, ready to run (only when ok)
    reason: str = ""    # why it was rejected (only when not ok)


def strip_fences(raw: str) -> str:
    """Remove markdown code fences an LLM may have wrapped the SQL in."""
    return FENCE_RE.sub("", raw.strip()).strip()


def _scrub(sql: str) -> str:
    """Blank out comments and string literals so keyword checks don't trip
    over content. 'DROP' inside a WHERE clause is data, not a command."""
    sql = BLOCK_COMMENT_RE.sub(" ", sql)
    sql = LINE_COMMENT_RE.sub(" ", sql)
    return STRING_LITERAL_RE.sub("''", sql)


def enforce_limit(sql: str, max_rows: int = MAX_ROWS) -> str:
    """Append a LIMIT if the query has none, so a stray query can't dump
    the whole table into the terminal."""
    if LIMIT_RE.search(_scrub(sql)):
        return sql
    return f"{sql.rstrip().rstrip(';')}\nLIMIT {max_rows}"


def validate(raw_sql: str, max_rows: int = MAX_ROWS) -> Verdict:
    """Return a Verdict describing whether this SQL is safe to show and run."""
    sql = strip_fences(raw_sql)
    if not sql:
        return Verdict(False, reason="The model returned no SQL at all.")

    scrubbed = _scrub(sql)

    # One statement only. Anything after the first ';' is a smuggled command.
    body, _, tail = scrubbed.partition(";")
    if tail.strip():
        return Verdict(
            False,
            reason="More than one SQL statement was returned; only a single "
                   "query is allowed.",
        )

    if not re.match(r"^\s*(SELECT|WITH)\b", body, re.IGNORECASE):
        return Verdict(
            False,
            reason="Only SELECT (or WITH ... SELECT) queries are allowed.",
        )

    hit = FORBIDDEN_RE.search(body)
    if hit:
        return Verdict(
            False,
            reason=f"Query contains the forbidden keyword {hit.group(1).upper()}.",
        )

    # Drop the trailing semicolon, then guarantee a row cap.
    cleaned = sql.strip().rstrip(";").strip()
    return Verdict(True, sql=enforce_limit(cleaned, max_rows))


# --------------------------------------------------------------------------
# Run `python -m agent.guards` from the project root to check these pass.
# --------------------------------------------------------------------------
CASES = [
    ("SELECT title FROM books",                      True,  "plain select"),
    ("select * from books;",                         True,  "lowercase + semicolon"),
    ("```sql\nSELECT 1\n```",                        True,  "markdown fenced"),
    ("WITH t AS (SELECT 1) SELECT * FROM t",         True,  "CTE"),
    ("SELECT title FROM books WHERE title='Drop it'", True, "keyword inside a string"),
    ("SELECT * FROM books LIMIT 5",                  True,  "existing limit kept"),
    ("DROP TABLE books",                             False, "destructive"),
    ("SELECT 1; DROP TABLE books",                   False, "stacked statements"),
    ("UPDATE books SET price = 0",                   False, "write"),
    ("PRAGMA table_info(books)",                     False, "pragma"),
    ("SELECT 1 -- ; DROP TABLE books",               True,  "comment is not a statement"),
    ("",                                             False, "empty"),
]

if __name__ == "__main__":
    failures = 0
    for sql, expected, label in CASES:
        v = validate(sql)
        mark = "PASS" if v.ok == expected else "FAIL"
        failures += mark == "FAIL"
        detail = v.reason if not v.ok else v.sql.replace("\n", " ")
        print(f"{mark}  {label:<32} -> {detail}")

    # LIMIT injection is the other behaviour worth asserting.
    assert "LIMIT 100" in validate("SELECT 1").sql
    assert "LIMIT 5" in validate("SELECT 1 LIMIT 5").sql
    assert "LIMIT 100" not in validate("SELECT 1 LIMIT 5").sql
    print(f"\n{len(CASES) - failures}/{len(CASES)} cases passed")
