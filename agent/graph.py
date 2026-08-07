"""The agent graph.

    load_approved -> plan_query -> validate_query -> approve -> execute
                          |              |               |          |
                          |              |               +----------+--> plan_query
                          |              +--> execute (previously approved)
                          +--> give_up            -> summarize -> write

A question a human has already approved skips generation and approval: the
saved SQL is replayed, though it still passes through the guards.

Every arrow that loops back carries a `feedback` string explaining what went
wrong, so a retry is a correction rather than a re-roll.
"""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from agent import nodes
from agent.nodes import State


def build_graph():
    g = StateGraph(State)

    g.add_node("load_approved", nodes.load_approved)
    g.add_node("plan_query", nodes.plan_query)
    g.add_node("validate_query", nodes.validate_query)
    g.add_node("approve", nodes.request_approval)
    g.add_node("execute", nodes.execute_query)
    g.add_node("summarize", nodes.summarize_result)
    g.add_node("write", nodes.write_output)
    g.add_node("give_up", nodes.give_up)

    g.add_edge(START, "load_approved")

    # straight to the guards if a human already approved this question
    g.add_conditional_edges("load_approved", nodes.after_load)

    g.add_edge("plan_query", "validate_query")

    # guards passed -> ask a human; failed -> retry or bail
    g.add_conditional_edges("validate_query", nodes.after_validate)

    # human said approve / edit / reject
    g.add_conditional_edges("approve", nodes.after_approval)

    # SQLite errors are just another kind of feedback
    g.add_conditional_edges("execute", nodes.after_execute)

    g.add_edge("summarize", "write")
    g.add_edge("write", END)
    g.add_edge("give_up", END)

    # The checkpointer is what makes the pause work: state is saved when the
    # graph interrupts, and restored when the human sends a decision back.
    return g.compile(checkpointer=MemorySaver())


if __name__ == "__main__":
    # `python -m agent.graph` prints the graph as Mermaid. Paste it into
    # https://mermaid.live to get a picture for your README.
    print(build_graph().get_graph().draw_mermaid())
