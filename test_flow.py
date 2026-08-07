"""End-to-end test of the agent loop with the model stubbed out.

Runs the real graph, the real guards, the real SQLite execution and the real
file writing -- only the two LLM calls are replaced with scripted answers.
So it needs no API key and no network:

    python test_flow.py

It walks the awkward paths on purpose: a query the guards reject, a human
rejection, a human edit, and finally an approval.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from langgraph.types import Command

from agent import llm, nodes

ROOT = Path(__file__).parent

# What the "model" returns, in order. The first is unsafe on purpose.
SCRIPTED_SQL = [
    "DROP TABLE books",                                    # guards reject this
    "SELECT title FROM books LIMIT 3",                     # human rejects this
    "SELECT genre, COUNT(*) AS n FROM books GROUP BY genre",  # human edits this
]

# The decisions a human would make at each pause.
SCRIPTED_DECISIONS = [
    {"action": "reject", "feedback": "I asked about revenue, not titles."},
    {"action": "edit",
     "sql": "SELECT b.genre, ROUND(SUM(oi.quantity * oi.unit_price), 2) AS revenue\n"
            "FROM order_items oi\n"
            "JOIN books b ON b.book_id = oi.book_id\n"
            "GROUP BY b.genre ORDER BY revenue DESC"},
    {"action": "approve"},
]


def main() -> int:
    if not (ROOT / "bookstore.db").exists():
        print("bookstore.db missing -- run `python seed.py` first.")
        return 1

    calls = {"sql": 0}

    def fake_generate_sql(question, schema, feedback=None):
        assert "CREATE TABLE books" in schema, "schema was not passed to the model"
        i = calls["sql"]
        calls["sql"] += 1
        return SCRIPTED_SQL[min(i, len(SCRIPTED_SQL) - 1)]

    def fake_summarize(question, sql, columns, rows):
        return f"[stubbed summary] {len(rows)} rows over columns {columns}."

    llm.generate_sql = fake_generate_sql
    llm.summarize = fake_summarize

    # Import after patching so the graph picks up the stubs.
    from agent.graph import build_graph

    graph = build_graph()
    config = {"configurable": {"thread_id": "test-flow"}}
    state = graph.invoke({"question": "Which genre made the most revenue?"}, config)

    pauses = 0
    while "__interrupt__" in state:
        payload = state["__interrupt__"][0].value
        print(f"\n  PAUSED for approval #{pauses + 1}:")
        print(f"    {payload['sql'].splitlines()[0]} ...")
        decision = SCRIPTED_DECISIONS[pauses]
        print(f"    human says: {decision['action']}")
        state = graph.invoke(Command(resume=decision), config)
        pauses += 1
        if pauses > 5:
            print("  Too many pauses; aborting.")
            return 1

    print("\n  --- assertions ---")
    checks = [
        ("guards blocked the unsafe query", calls["sql"] >= 2),
        ("human rejection triggered a retry", calls["sql"] == 3),
        ("three approval pauses happened", pauses == 3),
        ("the edited SQL is what ran", "unit_price" in state.get("sql", "")),
        ("rows came back", len(state.get("rows", [])) > 0),
        ("an answer was written", bool(state.get("answer"))),
        ("output directory exists", Path(state.get("output_dir", "/nope")).is_dir()),
    ]
    for label, passed in checks:
        print(f"  {'PASS' if passed else 'FAIL'}  {label}")

    out = Path(state["output_dir"])
    for name in ("query.sql", "result.csv", "answer.md"):
        exists = (out / name).exists()
        checks.append((f"{name} written", exists))
        print(f"  {'PASS' if exists else 'FAIL'}  {name} written")

    failed = [label for label, ok in checks if not ok]
    print(f"\n  {len(checks) - len(failed)}/{len(checks)} checks passed")

    # Clean up the artefacts this test produced.
    shutil.rmtree(out, ignore_errors=True)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
