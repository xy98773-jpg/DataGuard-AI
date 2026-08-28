"""LangGraph nodes — one responsibility per node.

Phase 2 full graph:
    START -> supervisor -(route)-> profiler -> inspector -> planner
          -> plan_validator -(PASS)-> risk -> execution -> validator
          -(PASS)-> END | -(FAIL)-> reflection -> planner (re-plan, MAX_ITERATION)

Each node emits real trace events (no synthetic data).
"""

from io import BytesIO

import pandas as pd
from langgraph.types import interrupt
from loguru import logger

from app.agents import InspectorAgent, PlannerAgent, ProfilerAgent, SupervisorAgent
from app.config import settings
from app.governance.evidence import build_evidence
from app.governance.execution import ExecutionEngine
from app.governance.plan_validator import PlanValidator
from app.governance.risk_engine import RiskEngine
from app.governance.validator import QualityValidator
from app.schemas.common import EventType, ExecutionMode
from app.schemas.dataset import DatasetProfile
from app.schemas.evidence import Evidence
from app.schemas.issue import Issue
from app.schemas.plan import CleaningPlan
from app.schemas.state import DataGovernanceState
from app.storage.object_store import get_object_storage
from app.tools.data.loader import load_dataframe
from app.tools.registry import get_registry
from app.trace import Stopwatch, get_collector

# --- agent factories (monkeypatch-able for tests) ---


def _profiler_factory() -> ProfilerAgent:
    return ProfilerAgent()


def _inspector_factory() -> InspectorAgent:
    return InspectorAgent()


def _planner_factory() -> PlannerAgent:
    return PlannerAgent()


def _supervisor_factory() -> SupervisorAgent:
    return SupervisorAgent()


def _emit(state, node, event_type, *, input=None, output=None, latency=0.0, tokens=0, status="success"):
    get_collector().emit(
        run_id=state["run_id"],
        node=node,
        event_type=event_type,
        input=input or {},
        output=output or {},
        latency=latency,
        tokens=tokens,
        status=status,
    )


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def supervisor_node(state: DataGovernanceState) -> dict:
    node = "supervisor"
    collector_sw = Stopwatch()
    _emit(
        state, node, EventType.AGENT_START,
        input={"user_request": state["user_request"], "source_type": state["source_type"]},
    )
    output, usage = _supervisor_factory().run(state["user_request"], state["source_type"])
    _emit(
        state, node, EventType.AGENT_DECISION,
        output=output.model_dump(),
        latency=collector_sw.elapsed_ms,
        tokens=usage.total,
    )
    logger.debug(f"[node:{node}] route={output.route} next={output.next_node}")
    return {"supervisor_route": output.model_dump(), "current_node": node}


def profiler_node(state: DataGovernanceState) -> dict:
    node = "profiler"
    collector_sw = Stopwatch()
    dataset_id = state["dataset_id"]
    ext = state.get("dataset_ext", "csv")

    _emit(state, node, EventType.AGENT_START, input={"dataset_id": dataset_id, "ext": ext})

    profile_tool = get_registry().get("profile_dataset")
    profile_dict = profile_tool.execute(
        dataset_id=dataset_id, ext=ext, source_type=state.get("source_type", "file")
    )
    _emit(
        state, node, EventType.TOOL_CALL,
        input={"tool": "profile_dataset", "dataset_id": dataset_id},
        output={"rows": profile_dict.get("rows"), "columns": profile_dict.get("columns")},
        latency=collector_sw.elapsed_ms,
    )
    profile = DatasetProfile.model_validate(profile_dict)

    evidence = build_evidence(dataset_id, profile, ext=ext, source_type=state.get("source_type", "file"))

    semantic, usage = _profiler_factory().run(profile)
    _emit(
        state, node, EventType.AGENT_DECISION,
        input={"profile_summary": {k: profile_dict.get(k) for k in ("rows", "columns", "anomalies")}},
        output=semantic.model_dump(),
        latency=collector_sw.elapsed_ms,
        tokens=usage.total,
    )
    logger.debug(f"[node:{node}] rows={profile.rows} anomalies={len(profile.anomalies)}")

    return {
        "schema_info": profile.schema,
        "profile_result": profile.model_dump(),
        "evidence": evidence.model_dump(),
        "current_node": node,
    }


def inspector_node(state: DataGovernanceState) -> dict:
    node = "inspector"
    collector_sw = Stopwatch()
    evidence = Evidence.model_validate(state["evidence"])

    _emit(state, node, EventType.AGENT_START, input={"evidence_keys": list(evidence.model_dump().keys())})
    report, usage = _inspector_factory().run(evidence)
    _emit(
        state, node, EventType.AGENT_DECISION,
        input={"candidate_anomalies": {k: len(v) for k, v in evidence.candidate_anomalies.items()}},
        output={"issues": [i.model_dump() for i in report.issues]},
        latency=collector_sw.elapsed_ms,
        tokens=usage.total,
    )
    logger.info(f"[node:{node}] found {len(report.issues)} issues")

    return {
        "issues": [i.model_dump() for i in report.issues],
        "current_node": node,
    }


def planner_node(state: DataGovernanceState) -> dict:
    node = "planner"
    collector_sw = Stopwatch()
    issues = [Issue.model_validate(i) for i in state["issues"]]

    # only executable cleaning tools are selectable (analysis tools excluded)
    registry = get_registry()
    executable_tools = [
        t for t in registry.list_tools() if hasattr(registry.get(t["name"]), "apply")
    ]
    context: dict = {
        "issues": [i.model_dump() for i in issues],
        "available_tools": executable_tools,
    }
    if state.get("plan_validation"):
        context["plan_feedback"] = state["plan_validation"]  # re-plan guidance

    _emit(state, node, EventType.AGENT_START, input={"issue_count": len(issues), "iteration": state.get("iteration", 0) + 1})
    plan, usage = _planner_factory().run(issues, context=context)
    _emit(
        state, node, EventType.AGENT_DECISION,
        input={"issues": [i.id for i in issues]},
        output=plan.model_dump(),
        latency=collector_sw.elapsed_ms,
        tokens=usage.total,
    )
    logger.info(f"[node:{node}] planned {len(plan.actions)} actions (iteration={state.get('iteration', 0) + 1})")

    return {
        "cleaning_plan": plan.model_dump(),
        "iteration": state.get("iteration", 0) + 1,
        "current_node": node,
    }


def plan_validator_node(state: DataGovernanceState) -> dict:
    node = "plan_validator"
    collector_sw = Stopwatch()
    plan = CleaningPlan.model_validate(state["cleaning_plan"])
    issues = [Issue.model_validate(i) for i in state.get("issues", [])]

    result = PlanValidator().validate(plan, issues, get_registry())
    _emit(
        state, node, EventType.VALIDATION,
        input={"actions": [a.tool for a in plan.actions]},
        output=result.model_dump(),
        latency=collector_sw.elapsed_ms,
    )
    logger.info(f"[node:{node}] status={result.status}")
    return {"plan_validation": result.model_dump(), "current_node": node}


def risk_node(state: DataGovernanceState) -> dict:
    node = "risk"
    collector_sw = Stopwatch()
    plan = CleaningPlan.model_validate(state["cleaning_plan"])

    assessment = RiskEngine().assess(plan, get_registry())
    approval_status = "PENDING" if assessment.requires_approval else "NOT_REQUIRED"
    _emit(
        state, node, EventType.AGENT_DECISION,
        input={"actions": [a.tool for a in plan.actions]},
        output=assessment.model_dump(),
        latency=collector_sw.elapsed_ms,
    )
    logger.info(f"[node:{node}] overall={assessment.overall_risk.value} requires_approval={assessment.requires_approval}")
    return {
        "risk_assessment": assessment.model_dump(),
        "approval_status": approval_status,
        "current_node": node,
    }


def execution_node(state: DataGovernanceState) -> dict:
    node = "execution"
    collector_sw = Stopwatch()
    plan = CleaningPlan.model_validate(state["cleaning_plan"])
    risk = state.get("risk_assessment") or {"actions": []}
    approval_status = state.get("approval_status", "NOT_REQUIRED")
    # 逐条审批结果：被拒绝的动作不执行
    approval_results = state.get("approval_results") or []
    rejected_ids = {r["id"] for r in approval_results if r.get("decision") == "reject"}
    if rejected_ids:
        kept = [a for a in plan.actions if f"{a.tool}__{a.column}" not in rejected_ids]
        plan = CleaningPlan(actions=kept)
        logger.info(f"[node:{node}] filtered {len(rejected_ids)} rejected action(s)")
    # policy -> execution mode:
    #   auto -> EXECUTE; approval -> EXECUTE only after APPROVED, else DRY_RUN preview
    mode_by_action: dict[str, ExecutionMode] = {}
    for a in risk.get("actions", []):
        if a.get("policy") == "auto":
            mode_by_action[a["tool"]] = ExecutionMode.EXECUTE
        elif approval_status == "APPROVED":
            mode_by_action[a["tool"]] = ExecutionMode.EXECUTE
        else:
            mode_by_action[a["tool"]] = ExecutionMode.DRY_RUN

    _emit(state, node, EventType.AGENT_START, input={"plan_actions": len(plan.actions), "approval_status": approval_status})
    engine = ExecutionEngine()
    result = engine.execute_plan(
        dataset_id=state["dataset_id"],
        plan=plan,
        ext=state.get("dataset_ext", "csv"),
        source_type=state.get("source_type", "file"),
        mode=ExecutionMode.EXECUTE,
        mode_by_action=mode_by_action,
        run_suffix=state.get("run_id", "").removeprefix("run_"),  # 影子表后缀（database 源写回用）
    )
    _emit(
        state, node, EventType.TOOL_RESULT,
        input={"actions": [a.tool for a in plan.actions]},
        output={"results": result["results"], "cleaned_key": result["cleaned_key"]},
        latency=collector_sw.elapsed_ms,
    )
    logger.info(f"[node:{node}] results={len(result['results'])} cleaned={result['cleaned_key']}")

    return {
        "execution_results": result["results"],
        "cleaned_key": result["cleaned_key"],
        "current_node": node,
    }


def validator_node(state: DataGovernanceState) -> dict:
    node = "validator"
    collector_sw = Stopwatch()
    dataset_id = state["dataset_id"]
    ext = state.get("dataset_ext", "csv")

    _emit(state, node, EventType.AGENT_START, input={"dataset_id": dataset_id})
    if state.get("source_type") == "database":
        from app.tools.data.loader import load_database_dataframe

        before_df = load_database_dataframe(dataset_id)
    else:
        before_df = load_dataframe(dataset_id, ext)

    cleaned_key = state.get("cleaned_key", "")
    if cleaned_key.startswith("shadow:"):
        # Shadow Table 策略：database 源清洗结果在影子表，从影子表读回做质量对比
        from app.services.database_service import DatabaseConnector
        from app.services.dataset_service import DatasetService

        shadow_table = cleaned_key.split(":", 1)[1]
        source = DatasetService().get_database_source(dataset_id)
        connector = DatabaseConnector(**source["connection"]) if source else None
        after_df = connector.fetch_table_dataframe(shadow_table) if connector else before_df
    elif cleaned_key:
        data = get_object_storage().load(cleaned_key)
        after_df = pd.read_csv(BytesIO(data))
    else:
        after_df = before_df

    result = QualityValidator().validate(before_df=before_df, after_df=after_df)
    _emit(
        state, node, EventType.VALIDATION,
        input={"cleaned_key": cleaned_key},
        output=result.model_dump(),
        latency=collector_sw.elapsed_ms,
    )
    logger.info(f"[node:{node}] status={result.status} before={result.quality_before.overall} after={result.quality_after.overall if result.quality_after else None}")

    return {
        "validation_result": result.model_dump(),
        "current_node": node,
    }


def reflection_node(state: DataGovernanceState) -> dict:
    node = "reflection"
    collector_sw = Stopwatch()
    validation = state.get("validation_result") or {}
    execution = state.get("execution_results") or []
    failed_exec = [r for r in execution if r.get("status") == "failed"]

    strategy = {
        "summary": "validation failed; adjust cleaning plan",
        "failed_executions": failed_exec,
        "validation_details": validation.get("details", []),
        "iteration": state.get("iteration", 0),
    }
    _emit(
        state, node, EventType.AGENT_DECISION,
        input={"validation_status": validation.get("status", "")},
        output=strategy,
        latency=collector_sw.elapsed_ms,
    )
    logger.info(f"[node:{node}] iteration={state.get('iteration', 0)}")
    return {"reflection": strategy, "current_node": node}


def approval_node(state: DataGovernanceState) -> dict:
    """Human-in-the-loop checkpoint.

    Pauses the workflow with LangGraph interrupt(), carrying a DRY_RUN
    preview (affected rows + before/after samples). The workflow resumes via
    Command(resume={"action": "approve"|"reject"}).
    """
    node = "approval"
    collector_sw = Stopwatch()
    plan = CleaningPlan.model_validate(state["cleaning_plan"])
    risk = state.get("risk_assessment") or {"actions": []}
    approval_actions = [a for a in risk.get("actions", []) if a.get("policy") == "approval"]

    # DRY_RUN preview for the approval-pending actions (no writes)
    engine = ExecutionEngine()
    preview_plan = CleaningPlan(
        actions=[a for a in plan.actions if any(ra["tool"] == a.tool for ra in approval_actions)]
    )
    if preview_plan.actions:
        preview = engine.execute_plan(
            dataset_id=state["dataset_id"],
            plan=preview_plan,
            ext=state.get("dataset_ext", "csv"),
            source_type=state.get("source_type", "file"),
            mode=ExecutionMode.DRY_RUN,
        )
        results = preview["results"]
    else:
        results = []

    requests = []
    for res in results:
        risk_of = next((ra["risk"] for ra in approval_actions if ra["tool"] == res["tool"]), "HIGH")
        requests.append(
            {
                "id": f"{res['tool']}__{res['column']}",
                "tool": res["tool"],
                "column": res["column"],
                "affected_rows": res.get("affected_rows", 0),
                "samples": res.get("samples", []),
                "risk": risk_of,
            }
        )

    _emit(state, node, EventType.HUMAN_APPROVAL, input={"requests": requests}, latency=collector_sw.elapsed_ms)

    decision = interrupt({"approval_requests": requests, "run_id": state["run_id"]})
    decision = decision or {}
    action = decision.get("action", "reject")

    # 逐条审批：decision.decisions = {"tool__column": "approve"|"reject"}
    # 兼容旧模式：无 decisions 时全部按 action 处理（全批准 / 全拒绝）
    decisions = decision.get("decisions")
    if decisions:
        results_list = [
            {
                "id": req["id"],
                "tool": req["tool"],
                "column": req["column"],
                "risk": req["risk"],
                "decision": decisions.get(req["id"], "reject"),
            }
            for req in requests
        ]
        approved_any = any(r["decision"] == "approve" for r in results_list)
    else:
        approved = action == "approve"
        results_list = [
            {
                "id": req["id"],
                "tool": req["tool"],
                "column": req["column"],
                "risk": req["risk"],
                "decision": "approve" if approved else "reject",
            }
            for req in requests
        ]
        approved_any = approved

    _emit(
        state, node, EventType.HUMAN_APPROVAL,
        output={"action": action, "results": results_list},
        latency=collector_sw.elapsed_ms,
    )
    logger.info(f"[node:{node}] decision={action} results={len(results_list)}")
    return {
        "approval_status": "APPROVED" if approved_any else "REJECTED",
        "approval_results": results_list,
        "current_node": node,
    }


# ---------------------------------------------------------------------------
# Conditional routing
# ---------------------------------------------------------------------------


def route_after_supervisor(state: DataGovernanceState) -> str:
    """Route by supervisor decision. Phase 2: file & database share profiler
    entry (database flow is split out in Phase 5)."""
    route = (state.get("supervisor_route") or {}).get("route", "file_cleaning")
    if route == "database_governance":
        return "database"
    return "profiler"


def route_after_plan_validator(state: DataGovernanceState) -> str:
    pv = state.get("plan_validation") or {}
    if pv.get("status") == "PASS":
        return "risk"
    if state.get("iteration", 0) >= settings.max_iteration:
        return "END"
    return "planner"


def route_after_risk(state: DataGovernanceState) -> str:
    risk = state.get("risk_assessment") or {}
    if risk.get("requires_approval"):
        return "approval"
    return "execution"


def route_after_approval(state: DataGovernanceState) -> str:
    if state.get("approval_status") == "APPROVED":
        return "execution"
    return "END"


def route_after_validator(state: DataGovernanceState) -> str:
    validation = state.get("validation_result") or {}
    if validation.get("status") == "PASS":
        return "END"
    if state.get("iteration", 0) >= settings.max_iteration:
        return "END"  # max re-plans reached -> requires human review (Phase 4)
    return "reflection"
