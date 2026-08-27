"""Pytest configuration.

Isolates tests from the dev database and forces FakeLLM:
- DG_DATABASE_URL           -> temp SQLite file (business DB)
- DG_DATASET_STORAGE_DIR    -> temp object storage root
- DG_LLM_PROVIDER=fake      -> offline deterministic LLM for tests/CI
- DG_WORKFLOW_EXECUTION_MODE=sync -> deterministic workflow runs in tests
"""

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

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pytest
from fastapi.testclient import TestClient

from app.tools import init_tools

init_tools()  # register tools for tests that bypass the app lifespan

from app.main import app  # noqa: E402
from app.storage.database import init_db  # noqa: E402

init_db()  # ensure business tables exist for tests using services directly


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c
