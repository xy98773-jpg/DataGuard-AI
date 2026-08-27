"""Database source API: MySQL/PostgreSQL connection, tables, schema, register.

Read-only by default; writes require Plan -> Risk -> Approval (Phase 5:
preview only, no write-back).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.database_service import DatabaseConnector
from app.services.dataset_service import DatasetService

router = APIRouter(tags=["database"])
_svc = DatasetService()


class ConnRequest(BaseModel):
    type: str = "mysql"  # mysql | postgresql
    host: str = "127.0.0.1"
    port: int = 3306
    database: str
    username: str
    password: str = ""


class SchemaRequest(ConnRequest):
    table: str


class RegisterRequest(SchemaRequest):
    name: str = ""


def _connector(req: ConnRequest) -> DatabaseConnector:
    return DatabaseConnector(req.type, req.host, req.port, req.database, req.username, req.password)


@router.post("/database/test")
def test_connection(req: ConnRequest) -> dict:
    try:
        return {"ok": _connector(req).test_connection(), "type": req.type}
    except Exception as exc:  # noqa: BLE001 - surface connection errors
        raise HTTPException(status_code=400, detail=f"connection failed: {exc}") from exc


@router.post("/database/tables")
def list_tables(req: ConnRequest) -> dict:
    try:
        return {"tables": _connector(req).list_tables()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/database/schema")
def get_schema(req: SchemaRequest) -> dict:
    try:
        return {"table": req.table, "columns": _connector(req).get_schema(req.table)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/database/preview")
def preview(req: SchemaRequest) -> dict:
    try:
        conn = _connector(req)
        rows = conn.sample_rows(req.table, limit=5)
        return {"table": req.table, "rows": rows}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/database/register")
def register(req: RegisterRequest) -> dict:
    try:
        conn_params = req.model_dump(exclude={"table", "name"})
        info = _svc.register_database(conn_params, req.table, req.name or req.table)
        return {"dataset_id": info.id, "filename": info.filename, "source_type": "database"}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
