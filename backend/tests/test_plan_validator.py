"""Unit tests: Plan Validator (anti-hallucination checks)."""

from app.governance.plan_validator import PlanValidator
from app.schemas.issue import Issue
from app.schemas.plan import CleaningPlan, PlanAction
from app.tools.registry import get_registry

ISSUES = [
    Issue(id="ISSUE001", issue_type="format_error", column="phone", severity="MEDIUM", confidence=0.9, affected_rows=5),
    Issue(id="ISSUE002", issue_type="format_error", column="email", severity="MEDIUM", confidence=0.9, affected_rows=3),
]


def test_valid_plan_passes():
    plan = CleaningPlan(actions=[PlanAction(tool="normalize_phone", column="phone", issue_id="ISSUE001")])
    result = PlanValidator().validate(plan, ISSUES, get_registry())
    assert result.status == "PASS"


def test_unregistered_tool_rejected():
    plan = CleaningPlan(actions=[PlanAction(tool="nonexistent_tool", column="phone", issue_id="ISSUE001")])
    result = PlanValidator().validate(plan, ISSUES, get_registry())
    assert result.status == "FAIL"
    assert any("not registered" in d for d in result.details)


def test_analysis_tool_rejected_as_cleaning_action():
    # detect_outlier is a registered analysis tool but not executable as cleaning
    plan = CleaningPlan(actions=[PlanAction(tool="detect_outlier", column="age", issue_id="ISSUE001")])
    result = PlanValidator().validate(plan, ISSUES, get_registry())
    assert result.status == "FAIL"
    assert any("not executable" in d for d in result.details)


def test_issue_column_mismatch_rejected():
    plan = CleaningPlan(actions=[PlanAction(tool="normalize_phone", column="email", issue_id="ISSUE001")])
    result = PlanValidator().validate(plan, ISSUES, get_registry())
    assert result.status == "FAIL"
    assert any("targets column" in d for d in result.details)


def test_unknown_issue_rejected():
    plan = CleaningPlan(actions=[PlanAction(tool="normalize_phone", column="phone", issue_id="ISSUE999")])
    result = PlanValidator().validate(plan, ISSUES, get_registry())
    assert result.status == "FAIL"
    assert any("issue not found" in d for d in result.details)


def test_empty_plan_passes():
    plan = CleaningPlan(actions=[])
    result = PlanValidator().validate(plan, ISSUES, get_registry())
    assert result.status == "PASS"
