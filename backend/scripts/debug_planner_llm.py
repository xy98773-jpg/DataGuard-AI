"""Debug: measure real DeepSeek planner-style call latency."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.client import get_llm_client  # noqa: E402
from app.schemas.plan import CleaningPlan  # noqa: E402

client = get_llm_client()
issues = [
    {
        "id": "ISSUE001",
        "issue_type": "format_error",
        "column": "phone",
        "severity": "MEDIUM",
        "confidence": 0.95,
        "affected_rows": 104,
        "evidence": ["138-1234-5678", "+86 13812345678"],
    },
    {
        "id": "ISSUE002",
        "issue_type": "missing_value",
        "column": "email",
        "severity": "MEDIUM",
        "confidence": 0.9,
        "affected_rows": 12,
        "evidence": [None],
    },
    {
        "id": "ISSUE003",
        "issue_type": "duplicate",
        "column": "customer_id",
        "severity": "HIGH",
        "confidence": 0.99,
        "affected_rows": 4,
        "evidence": ["C0098"],
    },
]
available_tools = [
    {"name": "normalize_phone", "description": "normalize chinese phone", "risk_level": "LOW"},
    {"name": "normalize_email", "description": "normalize email", "risk_level": "LOW"},
    {"name": "normalize_date", "description": "normalize date", "risk_level": "LOW"},
    {"name": "trim_whitespace", "description": "trim whitespace", "risk_level": "LOW"},
    {"name": "fill_missing", "description": "fill missing", "risk_level": "MEDIUM"},
    {"name": "delete_duplicate", "description": "delete duplicates", "risk_level": "HIGH"},
]

start = time.time()
try:
    out, usage = client.generate_structured(
        system=(
            "You are Cleaning Planner Agent. Generate a safe cleaning plan. "
            "Only use registered tools. Output JSON only with key actions "
            "(array of {tool, column, parameters, risk, issue_id})."
        ),
        user="Generate a cleaning plan for the reported issues.",
        schema=CleaningPlan,
        context={"issues": issues, "available_tools": available_tools},
    )
    print(f"OK in {time.time() - start:.1f}s")
    print(out.model_dump())
    print(usage.model_dump())
except Exception as exc:
    print(f"FAILED after {time.time() - start:.1f}s: {type(exc).__name__}: {exc}")
