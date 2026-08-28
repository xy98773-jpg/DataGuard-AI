"""Storage layer: SQLAlchemy engine/session for the *business* SQLite/Postgres DB.

Two storage concerns are strictly isolated:
- business DB  -> datasets, runs, issues, plans, trace, approvals ...
                 (SQLite locally; PostgreSQL/MySQL in production via DG_DATABASE_URL)
- checkpoints.db -> LangGraph checkpointer only (managed by langgraph)

The checkpointer DB is intentionally NOT created here; it is owned by the
LangGraph SqliteSaver in later phases.
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models (business DB)."""


def _create_engine(url: str):
    if url.startswith("sqlite"):
        return create_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    # PostgreSQL / MySQL (production): pool_pre_ping keeps connections healthy.
    return create_engine(url, echo=False, pool_pre_ping=True, pool_size=5, max_overflow=10)


engine = _create_engine(settings.business_db_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def ensure_storage_dirs() -> None:
    settings.dataset_storage_dir.mkdir(parents=True, exist_ok=True)
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    settings.app_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.checkpoint_db_path.parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    """Create all business tables if they do not exist (with lightweight migrations)."""
    ensure_storage_dirs()
    import app.models  # noqa: F401  (register models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    _migrate_add_column("datasets", "name", "VARCHAR(255) DEFAULT ''")
    # LLMSetting fallback 列（幂等）
    _migrate_add_column("llm_settings", "fallback_model", "VARCHAR(255) DEFAULT ''")
    _migrate_add_column("llm_settings", "fallback_base_url", "VARCHAR(500) DEFAULT ''")
    _migrate_add_column("llm_settings", "fallback_api_key", "VARCHAR(500) DEFAULT ''")
    _ensure_admin_user()


def _ensure_admin_user() -> None:
    """首次启动初始化管理员账号（无则创建）。"""
    from app.services.auth_service import ensure_admin
    ensure_admin()


def _migrate_add_column(table: str, column: str, ddl_type: str) -> None:
    """Idempotent SQLite migration: add a column if it does not exist."""
    if not settings.business_db_url.startswith("sqlite"):
        return
    from sqlalchemy import inspect

    inspector = inspect(engine)
    if column not in {c["name"] for c in inspector.get_columns(table)}:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}")
        import logging

        logging.getLogger("dataguard").info("migrated: added %s.%s", table, column)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
