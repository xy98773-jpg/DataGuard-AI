"""FakeLLM — deterministic offline LLM.

ONLY for unit tests / CI / offline dev; it is NOT a production run mode and
must never fake real reasoning in the final demo. The default LLM path is the
cloud OpenAI-Compatible API (see app/llm/providers.py).
"""

from app.llm.client import LLMClient, LLMUsage
from app.schemas.agents import SemanticProfile, SupervisorOutput
from app.schemas.common import Severity
from app.schemas.issue import IssueReport
from app.schemas.plan import CleaningPlan
from app.tools.registry import get_registry

_ISSUE_META = {
    "missing": ("missing_value", Severity.MEDIUM),
    "duplicate": ("duplicate", Severity.HIGH),
    "pattern": ("format_error", Severity.MEDIUM),
    "outlier": ("outlier", Severity.LOW),
}

_SEMANTICS = {
    "customer_id": "客户唯一标识",
    "name": "客户姓名",
    "phone": "客户手机号",
    "email": "客户邮箱",
    "age": "客户年龄",
    "register_date": "注册日期",
    "amount": "消费金额",
}


class FakeLLM(LLMClient):
    def generate_structured(self, *, system, user, schema, context=None):
        context = context or {}
        if schema is SupervisorOutput:
            data = self._supervisor(context)
        elif schema is SemanticProfile:
            data = self._profiler(context)
        elif schema is IssueReport:
            data = self._inspector(context)
        elif schema is CleaningPlan:
            data = self._planner(context)
        else:
            raise ValueError(f"FakeLLM does not know schema: {schema.__name__}")
        return schema.model_validate(data), LLMUsage(prompt_tokens=120, completion_tokens=60)

    # ---- deterministic "reasoning" per agent ----

    @staticmethod
    def _supervisor(context: dict) -> dict:
        source_type = context.get("source_type", "file")
        route = "file_cleaning" if source_type in ("file", "web") else "database_governance"
        return {
            "next_node": "profiler",
            "route": route,
            "reasoning": f"source_type={source_type} -> route {route}",
        }

    @staticmethod
    def _profiler(context: dict) -> dict:
        profile = context.get("profile") or {}
        rows, columns = profile.get("rows", 0), profile.get("columns", 0)
        schema = profile.get("schema") or {}
        anomalies = profile.get("anomalies") or {}
        cols = ", ".join(list(schema.keys())[:6])
        summary = f"数据集共 {rows} 行、{columns} 列，字段：{cols}。"
        if anomalies:
            summary += " 检测到候选质量问题，需要进一步检查。"
        column_semantics = {
            col: _SEMANTICS.get(col, "待人工确认") for col in schema if col in _SEMANTICS
        }
        notable = []
        for col, col_anomalies in anomalies.items():
            for a in col_anomalies:
                notable.append(f"{col}: {a.get('anomaly_type')} x {a.get('count', 0)}")
        return {
            "summary": summary,
            "column_semantics": column_semantics,
            "notable_patterns": notable[:5],
        }

    @staticmethod
    def _inspector(context: dict) -> dict:
        evidence = context.get("evidence") or {}
        anomalies = evidence.get("candidate_anomalies") or {}
        issues = []
        idx = 1
        for column, anomaly_list in anomalies.items():
            for anomaly in anomaly_list:
                atype = anomaly.get("anomaly_type")
                if atype not in _ISSUE_META:
                    continue
                count = anomaly.get("count", 0)
                if count <= 0:
                    continue
                issue_type, severity = _ISSUE_META[atype]
                issues.append(
                    {
                        "id": f"ISSUE{idx:03d}",
                        "issue_type": issue_type,
                        "column": column,
                        "severity": severity.value,
                        "confidence": 0.93,
                        "affected_rows": count,
                        "evidence": (anomaly.get("samples") or [])[:5],
                    }
                )
                idx += 1
        return {"issues": issues}

    @staticmethod
    def _planner(context: dict) -> dict:
        issues = context.get("issues") or []
        registry = get_registry()
        actions = []
        for issue in issues:
            tool_name = FakeLLM._match_tool(issue)
            if tool_name and registry.has(tool_name):
                tool = registry.get(tool_name)
                actions.append(
                    {
                        "tool": tool_name,
                        "column": issue.get("column", ""),
                        "parameters": {},
                        "risk": tool.risk_level.value,
                        "issue_id": issue.get("id"),
                    }
                )
        return {"actions": actions}

    @staticmethod
    def _match_tool(issue: dict) -> str | None:
        issue_type = issue.get("issue_type")
        column = (issue.get("column") or "").lower()
        if issue_type == "format_error":
            if "phone" in column:
                return "normalize_phone"
            if "email" in column:
                return "normalize_email"
            if "date" in column or "time" in column:
                return "normalize_date"
        if issue_type == "whitespace":
            return "trim_whitespace"
        if issue_type == "missing_value":
            return "fill_missing"
        if issue_type == "duplicate":
            # only delete duplicates on identifier-like columns
            if "id" in column or "key" in column:
                return "delete_duplicate"
            return None
        return None
