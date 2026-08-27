"""Database Connector — unified interface for MySQL / PostgreSQL.

Security rules:
- Default READ ONLY: write SQL (DROP/TRUNCATE/DELETE/ALTER/INSERT/UPDATE/...)
  is rejected by the SQL firewall; agents can never execute writes.
- Writes (Phase 5+): Plan -> Risk -> Approval -> Transaction / Shadow Table.
"""

import re

from sqlalchemy import create_engine, inspect, text

# statements forbidden by default (READ ONLY)
_WRITE_KEYWORDS = (
    "drop", "truncate", "delete", "alter", "insert", "update",
    "create", "grant", "revoke", "replace", "merge", "call",
)

_SELECT_START = re.compile(r"^\s*select\b", re.IGNORECASE)


class DatabaseConnector:
    def __init__(self, type: str = "mysql", host: str = "127.0.0.1", port: int = 3306, database: str = "", username: str = "", password: str = ""):
        self.db_type = type
        self._url = self._build_url(type, host, port, database, username, password)
        self._engine = create_engine(self._url, pool_pre_ping=True, pool_size=2, max_overflow=5)

    @staticmethod
    def _build_url(db_type: str, host: str, port: int, database: str, username: str, password: str) -> str:
        if db_type == "mysql":
            return f"mysql+pymysql://{username}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        if db_type == "postgresql":
            return f"postgresql+psycopg://{username}:{password}@{host}:{port}/{database}"
        raise ValueError(f"unsupported database type: {db_type}")

    # ---- read-only operations ----

    def test_connection(self) -> bool:
        with self._engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True

    def list_tables(self) -> list[str]:
        insp = inspect(self._engine)
        return insp.get_table_names()

    def get_schema(self, table: str) -> list[dict]:
        insp = inspect(self._engine)
        cols = insp.get_columns(table)
        return [
            {"name": c["name"], "type": str(c["type"]), "nullable": bool(c.get("nullable", True))}
            for c in cols
        ]

    def sample_rows(self, table: str, limit: int = 200) -> list[dict]:
        self._assert_safe_identifier(table)
        sql = f"SELECT * FROM {table} LIMIT :limit"
        with self._engine.connect() as conn:
            result = conn.execute(text(sql), {"limit": int(limit)})
            cols = list(result.keys())
            return [dict(zip(cols, [self._jsonable(v) for v in row])) for row in result.fetchall()]

    def preview_sql(self, sql: str, limit: int = 50) -> dict:
        """Read-only preview of a SELECT statement (SQL firewall enforced)."""
        self._assert_read_only(sql)
        with self._engine.connect() as conn:
            result = conn.execute(text(f"SELECT * FROM ({sql}) AS _preview LIMIT :limit"), {"limit": int(limit)})
            cols = list(result.keys())
            rows = [dict(zip(cols, [self._jsonable(v) for v in row])) for row in result.fetchall()]
        return {"columns": cols, "rows": rows}

    def fetch_table_dataframe(self, table: str, limit: int | None = None) -> "object":
        import pandas as pd

        rows = self.sample_rows(table, limit or 100_000)
        return pd.DataFrame(rows)

    # ---- safety ----

    @staticmethod
    def _assert_read_only(sql: str) -> None:
        stripped = sql.strip()
        if not stripped:
            raise PermissionError("empty SQL not allowed")
        if not _SELECT_START.match(stripped):
            raise PermissionError("only SELECT statements allowed (default READ ONLY)")
        # conservative: reject any forbidden keyword anywhere in the statement
        lowered = re.sub(r"[`'\"]", "", stripped).lower()
        for kw in _WRITE_KEYWORDS:
            if re.search(rf"\b{kw}\b", lowered):
                raise PermissionError(f"write SQL not allowed: {kw.upper()}")

    @staticmethod
    def _assert_safe_identifier(name: str) -> None:
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise PermissionError(f"unsafe identifier: {name!r}")

    @staticmethod
    def _jsonable(v):
        from decimal import Decimal

        if isinstance(v, Decimal):
            return float(v)
        if hasattr(v, "isoformat"):
            return v.isoformat()
        return v
