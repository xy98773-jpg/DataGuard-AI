"""Unit tests: Risk Engine (deterministic policy table, no LLM)."""

from app.governance.risk_engine import RISK_POLICY, RiskEngine
from app.schemas.plan import CleaningPlan, PlanAction
from app.tools.registry import get_registry


def test_risk_policy_table_has_expected_entries():
    assert RISK_POLICY["normalize_phone"].value == "LOW"
    assert RISK_POLICY["normalize_email"].value == "LOW"
    assert RISK_POLICY["normalize_date"].value == "LOW"
    assert RISK_POLICY["trim_whitespace"].value == "LOW"
    assert RISK_POLICY["fill_missing"].value == "MEDIUM"
    assert RISK_POLICY["fuzzy_match"].value == "MEDIUM"
    assert RISK_POLICY["delete_duplicate"].value == "HIGH"
    # delete_row is deliberately NOT implemented
    assert "delete_row" not in RISK_POLICY


def test_low_risk_auto_execute():
    plan = CleaningPlan(actions=[PlanAction(tool="normalize_phone", column="phone", issue_id="ISSUE001")])
    assessment = RiskEngine().assess(plan, get_registry())
    assert assessment.actions[0]["risk"] == "LOW"
    assert assessment.actions[0]["policy"] == "auto"
    assert assessment.requires_approval is False


def test_high_risk_requires_approval():
    plan = CleaningPlan(actions=[PlanAction(tool="delete_duplicate", column="customer_id", issue_id="ISSUE002")])
    assessment = RiskEngine().assess(plan, get_registry())
    assert assessment.actions[0]["risk"] == "HIGH"
    assert assessment.actions[0]["policy"] == "approval"
    assert assessment.requires_approval is True
    assert assessment.overall_risk.value == "HIGH"


def test_medium_risk_policy_configurable():
    plan = CleaningPlan(actions=[PlanAction(tool="fill_missing", column="email", issue_id="ISSUE003")])
    assessment = RiskEngine().assess(plan, get_registry())
    assert assessment.actions[0]["risk"] == "MEDIUM"
    assert assessment.actions[0]["policy"] in ("auto", "approval")
