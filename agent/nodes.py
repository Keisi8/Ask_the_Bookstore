"""The steps of the agent, one function per node.

Each node takes the state and returns only the keys it changes. Keeping them
as plain functions (rather than methods on a class) means each one can be
called directly in a test without building a graph.
"""

from __future__ import annotations

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

from langgraph.types import interrupt

from agent import approvals, guards, llm

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "bookstore.db"
OUTPUT_ROOT = ROOT / "outputs"
MAX_ATTEMPTS = 4


class State(TypedDict, total=False):
    """Everything the run carries between nodes."""
    question: str          # what the human asked
    schema: str            # CREATE TABLE statements, read from the live DB
    sql: str               # current candidate query
    feedback: str          # why the last attempt was rejected (drives retries)
    attempts: int          # how many queries we have generated so far
    decision: str          # approve | edit | reject, from the human
    columns: list[str]
    rows: list[tuple]
    answer: str            # written summary of the result
    output_dir: str        # where the artefacts landed
    error: str             # set when we give up
    run_dir: str           # batch mode: shared folder for the whole report
    kpi: str               # batch mode: short label for this question
    from_cache: bool       # this SQL came from a previous human approval
    approved_at: str       # when that approval happened
    review_all: bool       # ignore stored approvals and review everything


def _slug(text: str) -> str:
    """Filesystem-safe short name, e.g. 'Revenue trend' -> 'revenue-trend'."""
    cleaned = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower())
    return "-".join(cleaned.split())[:40] or "result"


# --------------------------------------------------------- stored approval
def load_approved(state: State) -> dict[str, Any]:
    """Reuse a query a human already approved for this exact question.

    The schema is read here so it can go into the cache key: an approval is
    only valid against the schema it was granted on.
    """
    schema = llm.get_schema(DB_PATH)
    if state.get("review_all"):
        return {"schema": schema, "from_cache": False}

    hit = approvals.lookup(state["question"], schema)
    if not hit:
        return {"schema": schema, "from_cache": False}

    print(f"  reusing the query you approved on {hit['approved_at'][:10]}")
    return {
        "schema": schema,
        "sql": hit["sql"],
        "from_cache": True,
        "approved_at": hit["approved_at"],
    }


def after_load(state: State) -> Literal["validate_query", "plan_query"]:
    # A cached query still goes through the guards: the file on disk is not
    # trusted more than the model is.
    return "validate_query" if state.get("from_cache") else "plan_query"


# ---------------------------------------------------------------- plan
def plan_query(state: State) -> dict[str, Any]:
    """Ask the model for SQL, passing along any rejection reason."""
    schema = state.get("schema") or llm.get_schema(DB_PATH)
    attempts = state.get("attempts", 0) + 1
    feedback = state.get("feedback", "")

    if feedback:
        print(f"\n  retrying (attempt {attempts}) with feedback: {feedback}")
    else:
        print("\n  writing a query...")

    sql = llm.generate_sql(state["question"], schema, feedback or None)
    # feedback is consumed here: it applied to the previous attempt only
    return {"sql": sql, "schema": schema, "attempts": attempts, "feedback": ""}


# ------------------------------------------------------------ validate
def validate_query(state: State) -> dict[str, Any]:
    """Run the safety guards. On failure, record why so the retry is informed."""
    verdict = guards.validate(state["sql"])
    if verdict.ok:
        return {"sql": verdict.sql, "feedback": ""}
    print(f"  guard rejected the query: {verdict.reason}")
    # If a stored approval no longer passes, drop back to generating a fresh
    # one, which will need a human again.
    return {"feedback": verdict.reason, "from_cache": False}


def after_validate(state: State) -> Literal["approve", "execute", "plan_query", "give_up"]:
    if not state.get("feedback"):
        # Already approved by a human on a previous run: run it directly.
        return "execute" if state.get("from_cache") else "approve"
    if state.get("attempts", 0) >= MAX_ATTEMPTS:
        return "give_up"
    return "plan_query"


# ------------------------------------------------------------- approve
def request_approval(state: State) -> dict[str, Any]:
    """Pause the run and hand control to the human.

    `interrupt` stops the graph here and surfaces this payload to whatever is
    driving it. The graph resumes only when a decision is sent back in, so
    nothing touches the database without a person saying so.
    """
    decision = interrupt(
        {
            "question": state["question"],
            "sql": state["sql"],
            "attempt": state.get("attempts", 1),
        }
    )
    action = decision.get("action", "reject")

    if action == "edit":
        # The human rewrote the SQL; it goes back through the guards, because
        # a human-supplied query is not automatically a safe one.
        return {"sql": decision["sql"], "decision": "edit", "feedback": ""}
    if action == "reject":
        return {
            "decision": "reject",
            "feedback": decision.get("feedback") or "The reviewer rejected the query.",
        }
    approvals.remember(
        state["question"], state["schema"], state["sql"], state.get("kpi", "")
    )
    print("  approved and saved; future runs will reuse this query.")
    return {"decision": "approve"}


def after_approval(state: State) -> Literal["execute", "validate_query", "plan_query", "give_up"]:
    decision = state.get("decision")
    if decision == "approve":
        return "execute"
    if decision == "edit":
        return "validate_query"
    if state.get("attempts", 0) >= MAX_ATTEMPTS:
        return "give_up"
    return "plan_query"


# ------------------------------------------------------------- execute
def execute_query(state: State) -> dict[str, Any]:
    """Run the approved SQL against a read-only connection.

    `mode=ro` is belt and braces alongside the guards: even if a destructive
    statement somehow got this far, SQLite itself would refuse it.
    """
    print("  running the query...")
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
        cursor = conn.execute(state["sql"])
        columns = [d[0] for d in cursor.description]
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as exc:
        print(f"  SQLite error: {exc}")
        return {"feedback": f"SQLite rejected the query with: {exc}"}
    return {"columns": columns, "rows": rows, "feedback": ""}


def after_execute(state: State) -> Literal["summarize", "plan_query", "give_up"]:
    if not state.get("feedback"):
        return "summarize"
    if state.get("attempts", 0) >= MAX_ATTEMPTS:
        return "give_up"
    return "plan_query"


# ----------------------------------------------------------- summarize
def summarize_result(state: State) -> dict[str, Any]:
    print(f"  {len(state['rows'])} row(s) returned, writing the summary...")
    answer = llm.summarize(
        state["question"], state["sql"], state["columns"], state["rows"]
    )
    return {"answer": answer}


# --------------------------------------------------------------- write
def write_output(state: State) -> dict[str, Any]:
    """Persist the run: the query, the rows, and the written answer.

    A single run gets its own timestamped folder. A batch run passes `run_dir`
    so every question lands in one shared report folder instead.
    """
    if state.get("run_dir"):
        out = Path(state["run_dir"]) / _slug(state.get("kpi") or state["question"])
    else:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out = OUTPUT_ROOT / stamp
        # Two questions asked in the same second must not overwrite each other.
        suffix = 2
        while out.exists():
            out = OUTPUT_ROOT / f"{stamp}_{suffix}"
            suffix += 1
    out.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    (out / "query.sql").write_text(state["sql"] + "\n", encoding="utf-8")

    with (out / "result.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(state["columns"])
        writer.writerows(state["rows"])

    (out / "answer.md").write_text(
        f"# {state['question']}\n\n"
        f"{state['answer']}\n\n"
        f"## Query\n\n```sql\n{state['sql']}\n```\n\n"
        f"## Result\n\n{_markdown_table(state['columns'], state['rows'])}\n"
        f"\n---\n_Generated {stamp} · {len(state['rows'])} row(s) · "
        f"approved by a human before execution._\n",
        encoding="utf-8",
    )
    return {"output_dir": str(out)}


def _markdown_table(columns: list[str], rows: list[tuple], limit: int = 20) -> str:
    head = "| " + " | ".join(columns) + " |"
    rule = "| " + " | ".join("---" for _ in columns) + " |"
    body = ["| " + " | ".join(str(v) for v in r) + " |" for r in rows[:limit]]
    if len(rows) > limit:
        body.append(f"| _... {len(rows) - limit} more rows in result.csv_ |"
                    + " |" * (len(columns) - 1))
    return "\n".join([head, rule, *body]) if rows else "_No rows returned._"


# -------------------------------------------------------------- giving up
def give_up(state: State) -> dict[str, Any]:
    reason = state.get("feedback", "unknown reason")
    print(f"\n  Giving up after {state.get('attempts')} attempts: {reason}")
    return {"error": reason}
