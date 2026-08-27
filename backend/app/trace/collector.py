"""Trace Collector — unified observability interface.

Phase 1: interface + SQLite-backed collector wired into agents/tools/workflow
(records into trace_events). Phase 3 adds the API + Workflow Studio UI.
Trace events are REAL run events — never synthetic demo data.
"""

import time
from abc import ABC, abstractmethod

from app.schemas.common import EventType


class TraceCollector(ABC):
    @abstractmethod
    def emit(
        self,
        *,
        run_id: str,
        node: str,
        event_type: EventType,
        input: dict | None = None,
        output: dict | None = None,
        latency: float = 0.0,
        tokens: int = 0,
        status: str = "success",
    ) -> None:
        """Record one trace event."""


class SQLiteTraceCollector(TraceCollector):
    """Persists trace events into the business SQLite DB (trace_events table)."""

    def __init__(self) -> None:
        from app.storage.database import SessionLocal

        self._session_factory = SessionLocal

    def emit(
        self,
        *,
        run_id: str,
        node: str,
        event_type: EventType,
        input: dict | None = None,
        output: dict | None = None,
        latency: float = 0.0,
        tokens: int = 0,
        status: str = "success",
    ) -> None:
        from app.models import TraceEvent

        with self._session_factory() as session:
            session.add(
                TraceEvent(
                    run_id=run_id,
                    node=node,
                    event_type=event_type.value,
                    input=input or {},
                    output=output or {},
                    latency=latency,
                    tokens=tokens,
                    status=status,
                )
            )
            session.commit()


class NullTraceCollector(TraceCollector):
    """No-op collector (tests that don't care about persistence)."""

    def emit(self, **kwargs) -> None:
        return


_collector: TraceCollector | None = None


def get_collector() -> TraceCollector:
    global _collector
    if _collector is None:
        _collector = SQLiteTraceCollector()
    return _collector


def set_collector(collector: TraceCollector) -> None:
    """Override collector (used in tests)."""
    global _collector
    _collector = collector


class Stopwatch:
    """Tiny latency helper for trace points."""

    def __init__(self) -> None:
        self._start = time.perf_counter()

    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 2)
