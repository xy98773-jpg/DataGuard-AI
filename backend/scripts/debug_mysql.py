"""Debug: why mysql_available() returns False under pytest env."""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="dg_test_"))
os.environ["DG_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["DG_DATASET_STORAGE_DIR"] = str(_TMP / "datasets")
os.environ["DG_CHECKPOINT_DB_PATH"] = str(_TMP / "checkpoints.db")
os.environ["DG_LLM_PROVIDER"] = "fake"
os.environ["DG_WORKFLOW_EXECUTION_MODE"] = "sync"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.database_service import DatabaseConnector  # noqa: E402

try:
    c = DatabaseConnector("mysql", "127.0.0.1", 3306, "dataguard_test", "root", "root123")
    print("connect OK:", c.test_connection())
    print("tables:", c.list_tables())
except Exception:
    import traceback

    traceback.print_exc()
