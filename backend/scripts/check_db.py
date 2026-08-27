"""Dev utility: verify business DB tables and storage files.

Usage: python scripts/check_db.py
"""

import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings  # noqa: E402


def main() -> None:
    db_path = Path(settings.business_db_url.removeprefix("sqlite:///"))
    print(f"business DB : {db_path} (exists={db_path.exists()})")
    if not db_path.exists():
        print("FAIL: app.db not created yet (start backend first)")
        return

    con = sqlite3.connect(db_path)
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    con.close()

    expected = [
        "approvals", "cleaning_plans", "dataset_profiles", "datasets",
        "executions", "issues", "trace_events", "validations", "workflow_runs",
    ]
    missing = [t for t in expected if t not in tables]
    print(f"tables       : {tables}")
    if missing:
        print(f"FAIL: missing tables {missing}")
        return
    print("OK: all 9 business tables created")


if __name__ == "__main__":
    main()
