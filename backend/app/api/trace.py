"""Trace API: agent observability (Phase 3).

- GET /api/trace/{run_id}            -> all events (optionally ?node=xxx)
- GET /api/trace/{run_id}/usage      -> token usage aggregated per node

All events come from REAL workflow runs (never synthetic).
"""

from fastapi import APIRouter, Query

from app.models import TraceEvent
from app.storage.database import SessionLocal

router = APIRouter(tags=["trace"])


def _serialize(row: TraceEvent) -> dict:
    return {
        "id": row.id,
        "run_id": row.run_id,
        "node": row.node,
        "event_type": row.event_type,
        "input": row.input,
        "output": row.output,
        "latency": row.latency,
        "tokens": row.tokens,
        "status": row.status,
        "created_at": row.created_at.isoformat() if row.created_at else "",
    }


@router.get("/trace/{run_id}")
def get_trace(run_id: str, node: str | None = Query(default=None)) -> dict:
    with SessionLocal() as session:
        q = session.query(TraceEvent).filter(TraceEvent.run_id == run_id)
        if node:
            q = q.filter(TraceEvent.node == node)
        rows = q.order_by(TraceEvent.id.asc()).all()
        return {"run_id": run_id, "node": node, "events": [_serialize(r) for r in rows]}


@router.get("/trace/{run_id}/usage")
def get_usage(run_id: str) -> dict:
    with SessionLocal() as session:
        rows = (
            session.query(TraceEvent)
            .filter(TraceEvent.run_id == run_id, TraceEvent.event_type == "AGENT_DECISION")
            .all()
        )
    per_node: dict[str, int] = {}
    for r in rows:
        per_node[r.node] = per_node.get(r.node, 0) + (r.tokens or 0)
    return {"run_id": run_id, "usage": per_node, "total": sum(per_node.values())}
