"""Ask the bookstore a question.

    python main.py "which genre made the most revenue in 2025?"
    python main.py                      # prompts for a question

The agent writes SQL, shows it to you, and waits. Nothing runs against the
database until you approve it.
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime
from pathlib import Path

from langgraph.types import Command

from agent import approvals
from agent.graph import build_graph

ROOT = Path(__file__).parent

BANNER = r"""
  Ask the Bookstore  ·  human-in-the-loop SQL agent
  --------------------------------------------------
"""

EXAMPLES = [
    "Which genre made the most revenue in 2025?",
    "Who are the top 5 authors by copies sold?",
    "Which city spends the most per customer?",
    "How does average order value compare across web, in-store and phone?",
    "Which books have never been ordered?",
]


def prompt_for_decision(payload: dict) -> dict:
    """Show the proposed SQL and collect the human's verdict."""
    print("\n" + "=" * 62)
    print(f"  REVIEW REQUIRED  (attempt {payload.get('attempt', 1)})")
    print("=" * 62)
    print(f"\n  Question: {payload['question']}\n")
    print("  Proposed query:\n")
    for line in payload["sql"].splitlines():
        print(f"    {line}")
    print("\n" + "-" * 62)
    print("  [a] approve and run    [e] edit the SQL    [r] reject with feedback")

    while True:
        choice = input("  > ").strip().lower()

        if choice in ("a", "approve", ""):
            return {"action": "approve"}

        if choice in ("e", "edit"):
            print("\n  Enter your SQL. Finish with a blank line:\n")
            lines: list[str] = []
            while True:
                line = input("    ")
                if not line.strip():
                    break
                lines.append(line)
            if lines:
                return {"action": "edit", "sql": "\n".join(lines)}
            print("  Nothing entered.")
            continue

        if choice in ("r", "reject"):
            reason = input("  What was wrong with it? ").strip()
            return {"action": "reject", "feedback": reason or "Not what I asked for."}

        print("  Please answer a, e or r.")


def run_question(graph, question: str, extra: dict | None = None) -> dict:
    """Drive one question through the graph, pausing for approval as needed."""
    # Each run gets its own thread id; the checkpointer uses it to restore
    # state when we resume after the interrupt.
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    state = graph.invoke({"question": question, **(extra or {})}, config)

    # The graph pauses every time it wants approval, which may be more than
    # once if you reject an attempt.
    while "__interrupt__" in state:
        payload = state["__interrupt__"][0].value
        decision = prompt_for_decision(payload)
        state = graph.invoke(Command(resume=decision), config)
    return state


def run_batch(review_all: bool = False):
    """Run the standing KPI questions from questions.yml as a single report.

    Returns the report folder so the caller can offer follow-up questions."""
    import yaml

    spec_path = ROOT / "questions.yml"
    if not spec_path.exists():
        raise FileNotFoundError("questions.yml not found next to main.py.")
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    items = spec.get("questions", [])
    if not items:
        raise RuntimeError("questions.yml contains no questions.")

    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = ROOT / "outputs" / f"report_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    title = spec.get("title", "Report")
    print(f"  {title}: {len(items)} KPIs, each needs your approval.")
    print(f"  Writing to {run_dir}")

    graph = build_graph()
    results = []

    for i, item in enumerate(items, start=1):
        kpi = item.get("kpi", f"Question {i}")
        question = " ".join(item["question"].split())
        print("\n" + "#" * 62)
        print(f"  [{i}/{len(items)}]  {kpi}")
        print("#" * 62)

        state = run_question(
            graph, question,
            {"run_dir": str(run_dir), "kpi": kpi, "review_all": review_all},
        )
        results.append((kpi, question, state))

        if state.get("error"):
            print(f"  Not answered: {state['error']}")
        else:
            print(f"  Done: {len(state['rows'])} row(s)")

    _write_report(run_dir, title, stamp, results)
    ok = sum(1 for _, _, s in results if not s.get("error"))
    print("\n" + "=" * 62)
    print(f"  {ok}/{len(results)} KPIs answered.")
    print(f"  Report: {run_dir / 'REPORT.md'}\n")
    return run_dir


def _write_report(run_dir, title: str, stamp: str, results: list) -> None:
    """Stitch the individual answers into one index document."""
    lines = [
        f"# {title}", "",
        f"_Generated {stamp}. Every query below was reviewed and approved by "
        "a human before it ran._", "",
        "## Contents", "",
    ]
    for kpi, _, state in results:
        anchor = kpi.lower().replace(" ", "-")
        note = "" if not state.get("error") else " — not answered"
        lines.append(f"- [{kpi}](#{anchor}){note}")
    lines.append("")

    for kpi, question, state in results:
        lines += [f"## {kpi}", "", f"**Question:** {question}", ""]
        if state.get("error"):
            lines += [f"_Not answered: {state['error']}_", ""]
            continue
        lines += [
            state["answer"], "",
            "<details><summary>Query that ran</summary>", "",
            "```sql", state["sql"], "```", "", "</details>", "",
        ]
    (run_dir / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def report_single(state: dict) -> None:
    """Print the outcome of one ad-hoc question."""
    if state.get("error"):
        print(f"\n  Stopped without an answer: {state['error']}\n")
        return
    print("\n" + "=" * 62)
    print(f"\n{state['answer']}\n")
    print(f"  Saved to {state['output_dir']}")
    print("    query.sql · result.csv · answer.md\n")


def ask_loop(graph, run_dir=None) -> None:
    """Ask ad-hoc questions one after another until the user stops.

    When `run_dir` is given (i.e. we just finished a report), answers are
    filed alongside that report instead of in their own folder, so a
    follow-up investigation stays attached to what prompted it.
    """
    print("\n  Ad-hoc questions. Blank line or 'q' to finish.")
    print("  Ideas:\n")
    for example in EXAMPLES:
        print(f"    - {example}")

    while True:
        question = input("\n  Question: ").strip()
        if not question or question.lower() in ("q", "quit", "exit"):
            print("\n  Done.\n")
            return

        extra = {"review_all": review_all}
        if run_dir is not None:
            extra |= {"run_dir": str(run_dir), "kpi": f"follow-up {question[:30]}"}

        state = run_question(graph, question, extra)
        report_single(state)


def choose_mode() -> str:
    """Two-step entry: report first, ad-hoc questions second."""
    print("  What would you like to do?\n")
    print("    [1] Run the weekly KPI report  ")
    print("    [2] Ask a single question      ")
    print("    [q] Quit\n")
    print("  (previously approved questions run without asking again;")
    print("   use --review-all to review everything, --approvals to list)\n")
    while True:
        choice = input("  > ").strip().lower()
        if choice in ("1", "2", "q", "quit", "exit", ""):
            return "1" if choice == "" else choice
        print("  Please answer 1, 2 or q.")


def manage_approvals() -> None:
    """`--approvals` lists what has been approved, `--forget` clears it."""
    if "--forget" in sys.argv:
        removed = approvals.forget()
        print(f"  Cleared {removed} stored approval(s). "
              "Every question will need review again.\n")
        return
    stored = approvals.listing()
    if not stored:
        print("  No stored approvals yet. The first run of each question "
              "will ask for review.\n")
        return
    print(f"  {len(stored)} approved quer(y/ies):\n")
    for fp, item in stored:
        label = item.get("kpi") or item["question"][:48]
        print(f"    {item['approved_at'][:16]}  {label}")
        print(f"      {fp}  ·  {item['sql'].splitlines()[0][:60]}...")
    print("\n  Run with --review-all to review these again, "
          "or --forget to clear them.\n")


def main() -> None:
    print(BANNER)

    if "--approvals" in sys.argv or "--forget" in sys.argv:
        manage_approvals()
        return

    review_all = "--review-all" in sys.argv

    # Non-interactive entry points are unchanged.
    if "--batch" in sys.argv:
        run_batch(review_all)
        return
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if args:
        report_single(run_question(
            build_graph(), " ".join(args), {"review_all": review_all}
        ))
        return

    choice = choose_mode()
    if choice in ("q", "quit", "exit"):
        print("\n  Nothing run.\n")
        return

    if choice == "1":
        run_dir = run_batch(review_all)
        answer = input("  Ask follow-up questions about this data? [y/N] ")
        if answer.strip().lower().startswith("y"):
            ask_loop(build_graph(), run_dir)
        return

    ask_loop(build_graph())


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, FileNotFoundError) as exc:
        # Missing API key or un-seeded database: say so in one line.
        print(f"\n  {exc}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n  Cancelled. Nothing was run against the database.\n")
        sys.exit(130)
