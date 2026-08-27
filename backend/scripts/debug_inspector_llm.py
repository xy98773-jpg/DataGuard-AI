"""Debug: measure real DeepSeek inspector-style call latency."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm.client import get_llm_client  # noqa: E402
from app.schemas.evidence import Evidence  # noqa: E402
from app.schemas.issue import IssueReport  # noqa: E402

client = get_llm_client()
evidence = Evidence.model_validate(
    {
        "rows": 504,
        "columns": 7,
        "schema_summary": {
            "customer_id": {"dtype": "string", "null_rate": 0.0, "unique_rate": 0.992},
            "name": {"dtype": "string", "null_rate": 0.0, "unique_rate": 0.99},
            "phone": {"dtype": "string", "null_rate": 0.0, "unique_rate": 0.91},
            "email": {"dtype": "string", "null_rate": 0.024, "unique_rate": 0.95},
            "age": {"dtype": "numeric", "null_rate": 0.0, "unique_rate": 0.98},
            "register_date": {"dtype": "string", "null_rate": 0.0, "unique_rate": 0.99},
            "amount": {"dtype": "numeric", "null_rate": 0.0, "unique_rate": 0.98},
        },
        "statistics": {
            "age": {"min": -5.0, "max": 150.0, "mean": 41.5, "median": 41.0},
            "amount": {"min": 10.0, "max": 190000.0, "mean": 8200.0},
        },
        "sample_rows": [
            {"customer_id": "C0001", "name": "张三", "phone": "138-1234-5678", "email": "a@qq", "age": 65, "register_date": "2023/01/05", "amount": 295.73}
        ]
        * 5,
        "candidate_anomalies": {
            "phone": [
                {"anomaly_type": "pattern", "count": 104, "samples": ["138-1234-5678", "+86 13812345678", "138 1234 5678"]}
            ],
            "email": [
                {"anomaly_type": "missing", "count": 12, "samples": [None]},
                {"anomaly_type": "pattern", "count": 30, "samples": ["user1@qq", "user2@example"]},
            ],
            "age": [{"anomaly_type": "outlier", "count": 10, "samples": [-5.0, 150.0]}],
            "customer_id": [{"anomaly_type": "duplicate", "count": 4, "samples": [{"value": "C0098", "occurrences": 2}]}],
            "register_date": [{"anomaly_type": "pattern", "count": 55, "samples": ["2023/01/05", "05-12-2022"]}],
        },
    }
)

start = time.time()
try:
    out, usage = client.generate_structured(
        system=(
            "You are Data Quality Inspector Agent. Analyze the evidence, "
            "identify quality problems. Output JSON only with key issues "
            "(array of {id, issue_type, column, severity, confidence, "
            "affected_rows, evidence}). Every issue requires evidence."
        ),
        user="Inspect the evidence and report data quality issues.",
        schema=IssueReport,
        context={"evidence": evidence.model_dump()},
    )
    print(f"OK in {time.time() - start:.1f}s, issues={len(out.issues)}")
    print(usage.model_dump())
except Exception as exc:
    print(f"FAILED after {time.time() - start:.1f}s: {type(exc).__name__}: {exc}")
