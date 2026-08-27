"""Plan Validator — guards against agent hallucination.

Deterministic checks (no LLM):
1. every tool in the plan is registered in the Tool Registry;
2. tool parameters pass the tool's params_schema;
3. every action references an existing issue and targets the SAME column.
"""

from app.schemas.issue import Issue
from app.schemas.plan import CleaningPlan, PlanValidation
from app.tools.registry import ToolRegistry


class PlanValidator:
    def validate(
        self,
        plan: CleaningPlan,
        issues: list[Issue],
        registry: ToolRegistry,
    ) -> PlanValidation:
        details: list[str] = []
        failed = False

        if not plan.actions:
            return PlanValidation(
                status="PASS",
                reason="empty plan (no fixable issues)",
                details=["no actions to validate"],
            )

        for action in plan.actions:
            tool = registry.get(action.tool)
            if tool is None:
                failed = True
                details.append(f"tool not registered: {action.tool}")
                continue

            # analysis tools (profile/detect_*) cannot be executed as cleaning steps
            if not hasattr(tool, "apply"):
                failed = True
                details.append(f"tool not executable as cleaning action: {action.tool}")
                continue

            param_errors = tool.validate_params(action.parameters)
            if param_errors:
                failed = True
                details.append(f"{action.tool} invalid params: {'; '.join(param_errors)}")

            if action.issue_id:
                issue = next((i for i in issues if i.id == action.issue_id), None)
                if issue is None:
                    failed = True
                    details.append(f"issue not found: {action.issue_id}")
                elif issue.column != action.column:
                    failed = True
                    details.append(
                        f"issue {action.issue_id} targets column '{issue.column}', "
                        f"plan targets '{action.column}'"
                    )
            else:
                failed = True
                details.append(f"action {action.tool} missing issue_id reference")

        status = "FAIL" if failed else "PASS"
        reason = "" if not failed else "plan rejected: " + "; ".join(details[:3])
        return PlanValidation(status=status, reason=reason, details=details)
