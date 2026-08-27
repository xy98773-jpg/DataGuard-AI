"""Risk Engine — deterministic, code-based risk assessment.

LLM never decides risk. Every action's risk comes from the RISK_POLICY table
(overridable via tool's declared risk_level) and the execution policy:
- LOW    -> auto execute (configurable via DG_LOW_RISK_AUTO_EXECUTE)
- MEDIUM -> configurable (DG_MEDIUM_RISK_MODE: auto | approval)
- HIGH   -> always requires approval (Phase 4 wires the actual HITL interrupt)
"""

from pydantic import BaseModel, Field

from app.config import settings
from app.schemas.common import RiskLevel
from app.schemas.plan import CleaningPlan

# Risk policy table (Part 2, section 24). delete_row is intentionally absent:
# the tool is NOT implemented (per project decision).
RISK_POLICY: dict[str, RiskLevel] = {
    "trim_whitespace": RiskLevel.LOW,
    "normalize_phone": RiskLevel.LOW,
    "normalize_email": RiskLevel.LOW,
    "normalize_date": RiskLevel.LOW,
    "fill_missing": RiskLevel.MEDIUM,
    "fuzzy_match": RiskLevel.MEDIUM,
    "delete_duplicate": RiskLevel.HIGH,
}


class RiskAssessment(BaseModel):
    actions: list[dict] = Field(default_factory=list)  # {tool, column, risk, policy}
    overall_risk: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False


class RiskEngine:
    def assess(self, plan: CleaningPlan, registry) -> RiskAssessment:
        assessed: list[dict] = []
        requires_approval = False
        worst = RiskLevel.LOW

        for action in plan.actions:
            risk = RISK_POLICY.get(action.tool) or RiskLevel.LOW
            policy = self._policy_for(risk)
            if policy == "approval":
                requires_approval = True
            if RiskLevel_rank(risk) > RiskLevel_rank(worst):
                worst = risk
            assessed.append(
                {
                    "tool": action.tool,
                    "column": action.column,
                    "risk": risk.value,
                    "policy": policy,
                }
            )
        return RiskAssessment(
            actions=assessed,
            overall_risk=worst,
            requires_approval=requires_approval,
        )

    @staticmethod
    def _policy_for(risk: RiskLevel) -> str:
        if risk == RiskLevel.LOW:
            return "auto" if settings.low_risk_auto_execute else "approval"
        if risk == RiskLevel.MEDIUM:
            return settings.medium_risk_mode  # auto | approval
        return "approval"  # HIGH


def RiskLevel_rank(risk: RiskLevel) -> int:
    return {"LOW": 1, "MEDIUM": 2, "HIGH": 3}[risk.value]
