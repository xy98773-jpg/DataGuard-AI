"""Database source tests.

Unit: SQL firewall (READ ONLY by default).
Integration: local MySQL (docker dg-mysql) — skipped automatically when the
container is not running.
"""

import pytest

from app.services.database_service import DatabaseConnector
from app.services.dataset_service import DatasetService
from app.services.workflow_service import WorkflowService

MYSQL_CONN = dict(
    type="mysql",
    host="127.0.0.1",
    port=3306,
    database="dataguard_test",
    username="root",
    password="root123",
)


def mysql_available() -> bool:
    try:
        DatabaseConnector(**MYSQL_CONN).test_connection()
        return True
    except Exception as exc:  # noqa: BLE001
        import os

        if os.environ.get("DG_DEBUG_DB"):
            print(f"[mysql_available] {type(exc).__name__}: {exc}")
        return False


# ---- SQL firewall (unit, no DB needed) ----

def test_firewall_blocks_write_statements():
    for sql in (
        "DROP TABLE customer",
        "DELETE FROM customer",
        "INSERT INTO x VALUES (1)",
        "UPDATE customer SET x=1",
        "ALTER TABLE customer ADD c INT",
        "TRUNCATE TABLE customer",
    ):
        with pytest.raises(PermissionError):
            DatabaseConnector._assert_read_only(sql)


def test_firewall_allows_select():
    DatabaseConnector._assert_read_only("SELECT * FROM customer WHERE age > 18")


def test_firewall_rejects_non_select():
    with pytest.raises(PermissionError):
        DatabaseConnector._assert_read_only("SHOW TABLES")


# ---- integration (requires docker MySQL) ----

@pytest.fixture(scope="module")
def mysql_conn():
    try:
        ok = DatabaseConnector(**MYSQL_CONN).test_connection()
        if not ok:
            pytest.skip("MySQL test container not running")
        return DatabaseConnector(**MYSQL_CONN)
    except Exception as exc:  # noqa: BLE001
        print(f"\n[debug mysql_available] {type(exc).__name__}: {exc}")
        pytest.skip(f"MySQL test container not running ({type(exc).__name__}: {exc})")


def test_connect_and_list_tables(mysql_conn):
    assert mysql_conn.test_connection() is True
    assert "customer" in mysql_conn.list_tables()


def test_schema_and_sample(mysql_conn):
    schema = mysql_conn.get_schema("customer")
    assert any(c["name"] == "customer_id" for c in schema)
    rows = mysql_conn.sample_rows("customer", limit=10)
    assert len(rows) == 10
    assert "phone" in rows[0]


def test_database_governance_flow(mysql_conn):
    svc = DatasetService()
    info = svc.register_database(MYSQL_CONN, "customer", "mysql.customer")
    assert info.source_type == "database"

    wf = WorkflowService()
    run_id = wf.start(info.id, "govern mysql.customer")
    status = wf.get_status(run_id)
    if status["status"] == "WAITING_APPROVAL":
        wf.approve(run_id)
        status = wf.get_status(run_id)
    assert status["status"] == "SUCCESS"
    assert status["iteration"] >= 1


def test_shadow_table_write(mysql_conn):
    """影子表写入：生产表不变，影子表包含清洗后数据，重复运行幂等。"""
    import pandas as pd

    df = mysql_conn.fetch_table_dataframe("customer")
    before = len(mysql_conn.sample_rows("customer", limit=100_000))

    cleaned = df.copy()
    cleaned["name"] = cleaned["name"].astype(str).str.strip()
    info = mysql_conn.write_shadow_table(cleaned, "customer", "test01")
    assert info["shadow_table"] == "customer_agent_test01"
    assert info["rows"] == len(df)

    # 影子表可读回，生产表行数不变
    shadow_df = mysql_conn.fetch_table_dataframe("customer_agent_test01")
    assert len(shadow_df) == len(df)
    assert len(mysql_conn.sample_rows("customer", limit=100_000)) == before

    # 同一 suffix 重复运行幂等（DROP + 重建）
    mysql_conn.write_shadow_table(cleaned.head(5), "customer", "test01")
    assert len(mysql_conn.fetch_table_dataframe("customer_agent_test01")) == 5


def test_execution_database_writes_shadow_table(mysql_conn):
    """Execution Engine 对 database 源 EXECUTE：清洗结果写入影子表，不覆盖生产表。"""
    from app.governance.execution import ExecutionEngine
    from app.schemas.common import ExecutionMode, RiskLevel
    from app.schemas.plan import CleaningPlan, PlanAction

    svc = DatasetService()
    info = svc.register_database(MYSQL_CONN, "customer", "mysql.customer")

    plan = CleaningPlan(
        actions=[
            PlanAction(
                tool="trim_whitespace",
                column="name",
                parameters={},
                risk=RiskLevel.LOW,
            )
        ]
    )
    result = ExecutionEngine().execute_plan(
        dataset_id=info.id,
        plan=plan,
        ext="csv",
        source_type="database",
        mode=ExecutionMode.EXECUTE,
        run_suffix="tst02",
    )
    assert result["cleaned_key"].startswith("shadow:")
    shadow = result["cleaned_key"].split(":", 1)[1]
    assert shadow == "customer_agent_tst02"
    # 影子表真实存在且行数与生产表一致；生产表未被修改
    assert len(mysql_conn.fetch_table_dataframe(shadow)) == len(
        mysql_conn.fetch_table_dataframe("customer")
    )
    assert mysql_conn.sample_rows(shadow, limit=1)[0]  # 影子表有数据
