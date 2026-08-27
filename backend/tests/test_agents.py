"""Agent tests: FakeLLM structured outputs validate against Pydantic schemas."""

from app.agents import InspectorAgent, PlannerAgent, ProfilerAgent
from app.schemas.dataset import DatasetProfile
from app.schemas.evidence import Evidence
from app.schemas.issue import Issue


def test_profiler_agent_output_schema():
    profile = DatasetProfile.model_validate(
        {
            "rows": 10,
            "columns": 3,
            "schema": {
                "phone": {"name": "phone", "dtype": "string", "null_rate": 0.1, "unique_rate": 0.9},
                "age": {"name": "age", "dtype": "numeric", "null_rate": 0.0, "unique_rate": 1.0},
            },
            "statistics": {"age": {"min": 18, "max": 65, "mean": 35}},
            "patterns": {},
            "anomalies": {"phone": [{"anomaly_type": "pattern", "count": 3, "samples": ["138-1234-5678"]}]},
        }
    )
    semantic, usage = ProfilerAgent().run(profile)
    assert semantic.summary
    assert semantic.column_semantics
    assert usage.total > 0


def test_inspector_agent_output_schema():
    evidence = Evidence.model_validate(
        {
            "rows": 100,
            "columns": 2,
            "schema_summary": {"phone": {"dtype": "string", "null_rate": 0.1, "unique_rate": 0.9}},
            "statistics": {},
            "sample_rows": [],
            "candidate_anomalies": {
                "phone": [{"anomaly_type": "pattern", "count": 12, "samples": ["138-1234-5678"]}]
            },
        }
    )
    report, usage = InspectorAgent().run(evidence)
    assert report.issues
    assert report.issues[0].id == "ISSUE001"
    assert report.issues[0].issue_type == "format_error"
    assert report.issues[0].confidence > 0.9
    assert usage.total > 0


def test_planner_agent_uses_registered_tools():
    issues = [
        Issue(
            id="ISSUE001",
            issue_type="format_error",
            column="phone",
            severity="MEDIUM",
            confidence=0.95,
            affected_rows=12,
            evidence=["138-1234-5678"],
        )
    ]
    plan, usage = PlannerAgent().run(issues)
    assert plan.actions
    assert plan.actions[0].tool == "normalize_phone"
    assert plan.actions[0].risk.value == "LOW"
    assert usage.total > 0


def test_planner_maps_duplicate_to_high_risk_tool():
    issues = [
        Issue(
            id="ISSUE002",
            issue_type="duplicate",
            column="customer_id",
            severity="HIGH",
            confidence=0.99,
            affected_rows=4,
            evidence=["C0001"],
        )
    ]
    plan, _ = PlannerAgent().run(issues)
    # Phase 4 registers delete_duplicate (HIGH) -> planner may propose it
    assert any(a.tool == "delete_duplicate" and a.risk.value == "HIGH" for a in plan.actions)
