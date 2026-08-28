"""Workflow service: create runs, execute the LangGraph workflow in the
background (never blocking the API request thread), persist results."""

import json
import threading
from uuid import uuid4

from langgraph.types import Command
from loguru import logger

from app.config import settings
from app.graph import build_graph
from app.models import (
    Approval as ApprovalRow,
    CleaningPlan as CleaningPlanRow,
    Execution as ExecutionRow,
    Issue as IssueRow,
    TraceEvent,
    Validation as ValidationRow,
    WorkflowRun,
)
from app.schemas.common import EventType
from app.schemas.state import DataGovernanceState
from app.services.dataset_service import DatasetService
from app.storage.database import SessionLocal
from app.storage.object_store import get_object_storage
from app.trace import get_collector

_NODE_ORDER = ["supervisor", "profiler", "inspector", "planner", "plan_validator", "risk", "approval", "execution", "validator", "reflection"]

# 并发控制：最多同时运行 N 个治理任务（防止资源抢占）
MAX_CONCURRENT_RUNS = 3
_active_runs_lock = threading.Lock()
_active_runs: set[str] = set()  # 当前正在执行的 run_id 集合
_cancel_flags: dict[str, bool] = {}  # 取消标记：run_id → True 表示已取消


class WorkflowService:
    def __init__(self) -> None:
        self._graph = build_graph()
        self._datasets = DatasetService()
        self._collector = get_collector()

    # ---- public API ----

    def start(self, dataset_id: str, goal: str) -> str:
        info = self._datasets.get_info(dataset_id)
        if info is None:
            raise ValueError(f"dataset not found: {dataset_id}")

        # 并发限制：超过上限则拒绝
        with _active_runs_lock:
            if len(_active_runs) >= MAX_CONCURRENT_RUNS:
                raise RuntimeError(f"已达到最大并发任务数 {MAX_CONCURRENT_RUNS}，请等待其他任务完成或取消现有任务")

        run_id = f"run_{uuid4().hex[:10]}"
        with SessionLocal() as session:
            session.add(
                WorkflowRun(
                    id=run_id,
                    dataset_id=dataset_id,
                    goal=goal,
                    status="PENDING",
                    current_node="supervisor",
                )
            )
            session.commit()

        if settings.workflow_execution_mode == "background":
            thread = threading.Thread(
                target=self._run,
                args=(run_id, dataset_id, goal),
                daemon=True,
                name=f"dg-workflow-{run_id}",
            )
            with _active_runs_lock:
                _active_runs.add(run_id)
            thread.start()
        else:
            with _active_runs_lock:
                _active_runs.add(run_id)
            self._run(run_id, dataset_id, goal)
        return run_id

    def cancel(self, run_id: str) -> bool:
        """取消任务：仅 PENDING/WAITING_APPROVAL/RUNNING 状态可取消。

        - PENDING：直接标记为 CANCELLED（线程还未真正开始）
        - WAITING_APPROVAL：标记为 CANCELLED（审批队列不再处理）
        - RUNNING：设置取消标记，线程在下一个节点检查时退出

        取消时**级联清理该 run 已产生的全部中间数据**（issues/plan/executions/
        validations/approvals/trace），避免取消后首页统计与问题列表残留脏数据；
        仅保留 workflow_runs 记录本身（状态 CANCELLED 作为审计痕迹）。
        """
        with SessionLocal() as session:
            row = session.get(WorkflowRun, run_id)
            if row is None:
                return False
            if row.status in ("SUCCESS", "FAILED", "CANCELLED"):
                return False  # 已终态，不可取消

            # 清理该 run 产生的中间数据（防止取消后污染首页统计/问题列表）
            session.query(IssueRow).filter(IssueRow.run_id == run_id).delete()
            session.query(CleaningPlanRow).filter(CleaningPlanRow.run_id == run_id).delete()
            session.query(ExecutionRow).filter(ExecutionRow.run_id == run_id).delete()
            session.query(ValidationRow).filter(ValidationRow.run_id == run_id).delete()
            session.query(ApprovalRow).filter(ApprovalRow.run_id == run_id).delete()
            session.query(TraceEvent).filter(TraceEvent.run_id == run_id).delete()

            row.status = "CANCELLED"
            session.commit()

            # 设置取消标记（RUNNING 状态线程会在节点间检查）
            _cancel_flags[run_id] = True

            # 从活跃集合移除
            with _active_runs_lock:
                _active_runs.discard(run_id)

            logger.info("任务已取消并清理中间数据: {}", run_id)
            return True

    def get_active_runs(self) -> list[dict]:
        """返回当前所有运行中/等待中的任务列表。"""
        with SessionLocal() as session:
            rows = (
                session.query(WorkflowRun)
                .filter(WorkflowRun.status.in_(["PENDING", "RUNNING", "WAITING_APPROVAL"]))
                .order_by(WorkflowRun.created_at.desc())
                .all()
            )
            return [
                {
                    "run_id": r.id,
                    "dataset_id": r.dataset_id,
                    "status": r.status,
                    "current_node": r.current_node,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

    def _is_cancelled(self, run_id: str) -> bool:
        """检查任务是否被取消（节点间调用）。"""
        return _cancel_flags.get(run_id, False)

    def get_status(self, run_id: str) -> dict:
        from app.models import TraceEvent

        with SessionLocal() as session:
            row = session.get(WorkflowRun, run_id)
            if row is None:
                return {"run_id": run_id, "status": "NOT_FOUND"}
            events = (
                session.query(TraceEvent)
                .filter(TraceEvent.run_id == run_id)
                .order_by(TraceEvent.id.asc())
                .all()
            )
        # 终态（SUCCESS/FAILED）进度固定 100%；其余按当前节点计算（reflection 为可选节点，置于末尾）
        if row.status in ("SUCCESS", "FAILED"):
            progress = 100
        else:
            progress = self._progress(row.current_node)
        return {
            "run_id": row.id,
            "dataset_id": row.dataset_id,
            "goal": row.goal,
            "status": row.status,
            "current_node": row.current_node,
            "iteration": row.iteration,
            "progress": progress,
            "nodes": _NODE_ORDER,
            "node_states": self._derive_node_states(events, _NODE_ORDER),
        }

    @staticmethod
    def _derive_node_states(events, nodes: list[str]) -> dict[str, str]:
        """Aggregate per-node status from real trace events.

        waiting -> AGENT_START seen -> running -> completion event -> success;
        any ERROR -> failed.
        """
        states: dict[str, str] = {n: "waiting" for n in nodes}
        for ev in events:
            node = ev.node
            if node not in states:
                continue
            if ev.event_type == "ERROR":
                states[node] = "failed"
            elif ev.event_type in (
                "AGENT_DECISION", "TOOL_RESULT", "VALIDATION", "HUMAN_APPROVAL",
            ):
                if states[node] != "failed":
                    states[node] = "success"
            elif ev.event_type == "AGENT_START":
                states[node] = "running"
        return states

    # ---- internals ----

    def _run(self, run_id: str, dataset_id: str, goal: str) -> None:
        try:
            info = self._datasets.get_info(dataset_id)
            source_type = info.source_type if info else "file"
            ext = self._datasets.get_ext(dataset_id)
            self._set_run(run_id, status="RUNNING", current_node="supervisor")
            self._collector.emit(
                run_id=run_id,
                node="workflow",
                event_type=EventType.WORKFLOW_START,
                input={"dataset_id": dataset_id, "goal": goal},
            )
            initial: DataGovernanceState = {
                "run_id": run_id,
                "user_request": goal,
                "source_type": source_type,
                "dataset_id": dataset_id,
                "dataset_ext": ext,
                "supervisor_route": {},
                "schema_info": {},
                "profile_result": {},
                "evidence": {},
                "issues": [],
                "cleaning_plan": {},
                "plan_validation": {},
                "risk_assessment": {},
                "execution_results": [],
                "cleaned_key": "",
                "validation_result": {},
                "reflection": {},
                "approval_status": "NOT_REQUIRED",
                "current_node": "supervisor",
                "iteration": 0,
                "trace_id": run_id,
            }
            config = {"configurable": {"thread_id": run_id}}

            # 检查是否被取消
            if self._is_cancelled(run_id):
                logger.info(f"workflow cancelled before start: {run_id}")
                return

            result = self._graph.invoke(initial, config=config)

            # 检查是否被取消
            if self._is_cancelled(run_id):
                logger.info(f"workflow cancelled after execution: {run_id}")
                return

            payload = self._extract_interrupt_payload(result)
            if payload is not None:
                self._persist(run_id, result)  # persist issues/plan even while paused
                self._save_pending_approvals(run_id, payload)
                self._set_run(run_id, status="WAITING_APPROVAL", current_node="approval")
                self._collector.emit(
                    run_id=run_id,
                    node="approval",
                    event_type=EventType.HUMAN_APPROVAL,
                    output={"status": "WAITING_APPROVAL", "requests": payload.get("approval_requests", [])},
                )
                logger.info(f"workflow paused: {run_id} WAITING_APPROVAL")
                return

            final_status = self._derive_final_status(result)
            self._persist(run_id, result)
            report_key = self._save_report(run_id, dataset_id, result)
            self._set_run(
                run_id,
                status=final_status,
                current_node="validator",
                iteration=result.get("iteration", 0),
            )
            self._collector.emit(
                run_id=run_id,
                node="workflow",
                event_type=EventType.WORKFLOW_END,
                output={"status": final_status, "report_key": report_key},
            )
            logger.info(f"workflow finished: {run_id} {final_status} (report={report_key})")
        except Exception as exc:  # noqa: BLE001 - all failures must be traced
            logger.exception(f"workflow failed: {run_id}")
            self._collector.emit(
                run_id=run_id,
                node="workflow",
                event_type=EventType.ERROR,
                output={"message": str(exc)},
                status="error",
            )
            self._set_run(run_id, status="FAILED")
        finally:
            # 清理：从活跃集合移除，清除取消标记
            with _active_runs_lock:
                _active_runs.discard(run_id)
            _cancel_flags.pop(run_id, None)

    # ---- human-in-the-loop ----

    def approve(self, run_id: str, operator: str = "") -> dict:
        return self._decide(run_id, "approve", operator)

    def reject(self, run_id: str, operator: str = "") -> dict:
        return self._decide(run_id, "reject", operator)

    def submit_decisions(self, run_id: str, decisions: dict, operator: str = "") -> dict:
        """逐条审批：decisions = {"tool__column": "approve"|"reject", ...}"""
        self._set_approval_decisions(run_id, decisions, operator)
        resume_decision = {"action": "submit", "decisions": decisions}
        if settings.workflow_execution_mode == "background":
            threading.Thread(
                target=self._resume,
                args=(run_id, resume_decision),
                daemon=True,
                name=f"dg-resume-{run_id}",
            ).start()
            return {"run_id": run_id, "status": "resumed", "decisions": decisions}
        return self._resume(run_id, resume_decision)

    def get_pending_approvals(self) -> list[dict]:
        with SessionLocal() as session:
            rows = (
                session.query(ApprovalRow)
                .join(WorkflowRun, ApprovalRow.run_id == WorkflowRun.id)
                .filter(
                    ApprovalRow.status == "PENDING",
                    WorkflowRun.status == "WAITING_APPROVAL",  # 只返回活跃等待审批的 run
                )
                .order_by(ApprovalRow.created_at.asc())
                .all()
            )
            return [
                {
                    "id": r.id,
                    "run_id": r.run_id,
                    "operation": json.loads(r.operation) if r.operation else {},
                    "status": r.status,
                    "operator": r.operator,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]

    def _decide(self, run_id: str, action: str, operator: str) -> dict:
        status = "APPROVED" if action == "approve" else "REJECTED"
        self._set_approval_status(run_id, status, operator)
        if settings.workflow_execution_mode == "background":
            threading.Thread(
                target=self._resume,
                args=(run_id, {"action": action}),
                daemon=True,
                name=f"dg-resume-{run_id}",
            ).start()
            return {"run_id": run_id, "status": "resumed", "decision": action}
        return self._resume(run_id, {"action": action})

    def _resume(self, run_id: str, decision: dict) -> dict:
        config = {"configurable": {"thread_id": run_id}}
        try:
            result = self._graph.invoke(Command(resume=decision), config=config)
        except Exception as exc:  # noqa: BLE001 - resume failures must be traced
            logger.exception(f"workflow resume failed: {run_id}")
            self._collector.emit(
                run_id=run_id, node="approval", event_type=EventType.ERROR,
                output={"message": str(exc)}, status="error",
            )
            self._set_run(run_id, status="FAILED")
            return {"run_id": run_id, "status": "FAILED"}

        payload = self._extract_interrupt_payload(result)
        if payload is not None:
            self._save_pending_approvals(run_id, payload)
            self._set_run(run_id, status="WAITING_APPROVAL", current_node="approval")
            return {"run_id": run_id, "status": "WAITING_APPROVAL"}

        final_status = self._derive_final_status(result)
        self._persist(run_id, result)
        report_key = self._save_report(run_id, result.get("dataset_id", ""), result)
        self._set_run(
            run_id,
            status=final_status,
            current_node="validator",
            iteration=result.get("iteration", 0),
        )
        self._collector.emit(
            run_id=run_id, node="workflow", event_type=EventType.WORKFLOW_END,
            output={"status": final_status, "report_key": report_key},
        )
        logger.info(f"workflow resumed & finished: {run_id} {final_status}")
        return {"run_id": run_id, "status": final_status}

    @staticmethod
    def _extract_interrupt_payload(result: dict):
        interrupts = result.get("__interrupt__")
        if not interrupts:
            return None
        first = interrupts[0] if isinstance(interrupts, (list, tuple)) else interrupts
        return getattr(first, "value", first)

    @staticmethod
    def _save_pending_approvals(run_id: str, payload: dict) -> None:
        requests = (payload or {}).get("approval_requests", [])
        if not requests:
            return
        with SessionLocal() as session:
            # 幂等：先清理该 run 尚未处理的 PENDING 旧行（已 APPROVED/REJECTED 保留，审批历史可追溯），
            # 避免同一次运行多次暂停时审批列表重复累积
            session.query(ApprovalRow).filter(
                ApprovalRow.run_id == run_id,
                ApprovalRow.status == "PENDING",
            ).delete()
            for req in requests:
                session.add(
                    ApprovalRow(
                        run_id=run_id,
                        operation=json.dumps(req, ensure_ascii=False),
                        status="PENDING",
                    )
                )
            session.commit()

    @staticmethod
    def _set_approval_status(run_id: str, status: str, operator: str) -> None:
        with SessionLocal() as session:
            rows = (
                session.query(ApprovalRow)
                .filter(ApprovalRow.run_id == run_id, ApprovalRow.status == "PENDING")
                .all()
            )
            for r in rows:
                r.status = status
                r.operator = operator
            session.commit()

    @staticmethod
    def _set_approval_decisions(run_id: str, decisions: dict, operator: str) -> None:
        """按 operation.id 逐条设置审批状态（approve -> APPROVED / reject -> REJECTED）."""
        with SessionLocal() as session:
            rows = (
                session.query(ApprovalRow)
                .filter(ApprovalRow.run_id == run_id, ApprovalRow.status == "PENDING")
                .all()
            )
            for r in rows:
                op = json.loads(r.operation) if r.operation else {}
                op_id = op.get("id")
                if op_id in decisions:
                    r.status = "APPROVED" if decisions[op_id] == "approve" else "REJECTED"
                    r.operator = operator
            session.commit()

    @staticmethod
    def _derive_final_status(state: DataGovernanceState) -> str:
        if state.get("approval_status") == "REJECTED":
            return "FAILED"  # human rejected the high-risk operation
        validation = state.get("validation_result") or {}
        plan_validation = state.get("plan_validation") or {}
        if plan_validation.get("status") == "FAIL":
            return "FAILED"  # unrecoverable plan (max re-plans reached)
        if validation.get("status") == "FAIL":
            return "FAILED"  # quality did not improve
        return "SUCCESS"

    def _save_report(self, run_id: str, dataset_id: str, state: DataGovernanceState) -> str:
        report = {
            "run_id": run_id,
            "dataset_id": dataset_id,
            "issues": state.get("issues", []),
            "plan": state.get("cleaning_plan", {}),
            "execution": state.get("execution_results", []),
            "validation": state.get("validation_result", {}),
        }
        key = f"outputs/{dataset_id}/validation_report.json"
        payload = json.dumps(report, ensure_ascii=False, default=str).encode("utf-8")
        get_object_storage().save(key, payload)
        return key

    def _persist(self, run_id: str, state: DataGovernanceState) -> None:
        with SessionLocal() as session:
            # idempotent: clear previous rows for this run (paused runs re-persist on resume)
            session.query(IssueRow).filter(IssueRow.run_id == run_id).delete()
            session.query(CleaningPlanRow).filter(CleaningPlanRow.run_id == run_id).delete()
            session.query(ValidationRow).filter(ValidationRow.run_id == run_id).delete()
            session.query(ExecutionRow).filter(ExecutionRow.run_id == run_id).delete()

            for issue in state.get("issues", []):
                session.add(
                    IssueRow(
                        run_id=run_id,
                        agent_issue_id=issue.get("id", ""),
                        issue_type=issue.get("issue_type", ""),
                        column_name=issue.get("column", ""),
                        severity=issue.get("severity", "LOW"),
                        confidence=float(issue.get("confidence", 0.0)),
                        affected_rows=int(issue.get("affected_rows", 0)),
                        evidence=issue.get("evidence", []),
                    )
                )
            plan = state.get("cleaning_plan") or {}
            actions = plan.get("actions", [])
            risk_level = max((a.get("risk", "LOW") for a in actions), default="LOW")
            session.add(
                CleaningPlanRow(
                    run_id=run_id,
                    plan=plan,
                    risk_level=risk_level,
                )
            )
            validation = state.get("validation_result") or {}
            before = (validation.get("quality_before") or {}).get("overall", 0.0)
            after = (validation.get("quality_after") or {}).get("overall", 0.0)
            session.add(
                ValidationRow(
                    run_id=run_id,
                    before_score=float(before),
                    after_score=float(after),
                    result=validation.get("status", ""),
                    details=validation.get("details", []),
                )
            )
            for exec_result in state.get("execution_results", []):
                session.add(
                    ExecutionRow(
                        run_id=run_id,
                        tool_name=exec_result.get("tool", ""),
                        input={"column": exec_result.get("column", "")},
                        output={
                            "affected_rows": exec_result.get("affected_rows", 0),
                            "samples": exec_result.get("samples", []),
                        },
                        status=exec_result.get("status", ""),
                        latency=0.0,
                    )
                )
            session.commit()

    @staticmethod
    def _set_run(run_id: str, *, status: str, current_node: str = "", iteration: int | None = None) -> None:
        with SessionLocal() as session:
            row = session.get(WorkflowRun, run_id)
            if row is None:
                return
            row.status = status
            if current_node:
                row.current_node = current_node
            if iteration is not None:
                row.iteration = iteration
            session.commit()

    @staticmethod
    def _progress(current_node: str) -> int:
        if current_node not in _NODE_ORDER:
            return 0
        return int((_NODE_ORDER.index(current_node) + 1) / len(_NODE_ORDER) * 100)
