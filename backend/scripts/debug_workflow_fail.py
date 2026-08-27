"""在 pytest 等价环境复现 workflow 失败，打印真实异常。"""
import os
import sys
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="dg_dbg_"))
os.environ["DG_DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["DG_DATASET_STORAGE_DIR"] = str(_TMP / "datasets")
os.environ["DG_CHECKPOINT_DB_PATH"] = str(_TMP / "checkpoints.db")
os.environ["DG_LLM_PROVIDER"] = "fake"
os.environ["DG_WORKFLOW_EXECUTION_MODE"] = "sync"
os.environ["DG_APP_DB_PATH"] = str(_TMP / "app.db")
sys.path.insert(0, ".")

from app.services.dataset_service import DatasetService  # noqa: E402
from app.services.workflow_service import WorkflowService  # noqa: E402
from app.storage.database import SessionLocal, init_db  # noqa: E402
from app.models import TraceEvent  # noqa: E402

init_db()

from app.tools.data import register_data_tools  # noqa: E402
from app.tools.cleaning import register_cleaning_tools  # noqa: E402

register_data_tools()
register_cleaning_tools()

svc = DatasetService()
with open("datasets/demo/customer.csv", "rb") as f:
    info = svc.save_upload("customer.csv", f.read())
print("ds:", info.id)

wf = WorkflowService()
try:
    run_id = wf.start(info.id, "clean")
    print("run:", run_id, wf.get_status(run_id))
except Exception as exc:
    import traceback

    traceback.print_exc()

# 查 trace ERROR
with SessionLocal() as s:
    rows = (
        s.query(TraceEvent)
        .filter(TraceEvent.event_type == "ERROR")
        .order_by(TraceEvent.id.desc())
        .limit(2)
        .all()
    )
    for r in rows:
        print("TRACE ERROR:", r.node, r.output)
