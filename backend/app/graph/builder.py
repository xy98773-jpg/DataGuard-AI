"""LangGraph workflow builder.

Phase 4 full graph (Human-in-the-loop):
    START -> supervisor -(route)-> profiler -> inspector -> planner
          -> plan_validator -(PASS)-> risk
          -(auto)-> execution -> validator -(PASS)-> END
          -(requires_approval)-> approval -(interrupt)-> resume
             APPROVED -> execution | REJECTED -> END
          -(FAIL & iteration<MAX)-> reflection -> planner (re-plan)
          -(FAIL & iteration>=MAX)-> END (human review)

Checkpointer: dedicated SQLite (checkpoints.db), separate from the business DB.
"""

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from app.config import settings
from app.graph.nodes import (
    approval_node,
    execution_node,
    inspector_node,
    plan_validator_node,
    planner_node,
    profiler_node,
    reflection_node,
    risk_node,
    route_after_approval,
    route_after_plan_validator,
    route_after_risk,
    route_after_supervisor,
    route_after_validator,
    supervisor_node,
    validator_node,
)
from app.schemas.state import DataGovernanceState


def _make_checkpointer():
    """Dedicated checkpointer DB (checkpoints.db), separate from business DB."""
    conn = sqlite3.connect(str(settings.checkpoint_db_path), check_same_thread=False)
    return SqliteSaver(conn)


def build_full_graph():
    """Build and compile the Phase 4 full workflow graph."""
    graph = StateGraph(DataGovernanceState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("profiler", profiler_node)
    graph.add_node("inspector", inspector_node)
    graph.add_node("planner", planner_node)
    graph.add_node("plan_validator", plan_validator_node)
    graph.add_node("risk", risk_node)
    graph.add_node("approval", approval_node)
    graph.add_node("execution", execution_node)
    graph.add_node("validator", validator_node)
    graph.add_node("reflection", reflection_node)

    graph.add_edge(START, "supervisor")
    graph.add_conditional_edges(
        "supervisor",
        route_after_supervisor,
        {"profiler": "profiler", "database": "profiler"},  # Phase 5: database -> db flow
    )
    graph.add_edge("profiler", "inspector")
    graph.add_edge("inspector", "planner")
    graph.add_edge("planner", "plan_validator")
    graph.add_conditional_edges(
        "plan_validator",
        route_after_plan_validator,
        {"risk": "risk", "planner": "planner", "END": END},
    )
    graph.add_conditional_edges(
        "risk",
        route_after_risk,
        {"approval": "approval", "execution": "execution"},
    )
    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {"execution": "execution", "END": END},
    )
    graph.add_edge("execution", "validator")
    graph.add_conditional_edges(
        "validator",
        route_after_validator,
        {"END": END, "reflection": "reflection"},
    )
    graph.add_edge("reflection", "planner")

    return graph.compile(checkpointer=_make_checkpointer())


def build_graph():
    """Entry point; returns the full workflow graph with checkpointer."""
    return build_full_graph()
