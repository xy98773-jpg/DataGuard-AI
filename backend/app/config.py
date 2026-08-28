"""Application configuration (Production-Ready).

All external dependencies are configurable via environment variables or
backend/.env (prefix DG_).  Never hardcode API keys, URLs, or timeouts in code.

Design rules (Architecture Specification):
- LLM: default = cloud OpenAI-Compatible API; `fake` ONLY for tests/CI/dev.
- Business DB: SQLite for local dev / tests; PostgreSQL/MySQL for production.
- Checkpoint DB: strictly separated from business DB (LangGraph checkpointer).
- Object storage: abstracted via ObjectStorage interface (local / S3-compatible).
- Redis: reserved in config; not required until a later phase (YAGNI).
"""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_prefix="DG_",
        extra="ignore",
    )

    # --- application ---
    app_name: str = "DataGuard AI"
    debug: bool = True
    api_prefix: str = "/api"

    # --- business database (SQLite local default; PG/MySQL in production) ---
    # e.g. DG_DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dataguard
    database_url: str = ""
    app_db_path: Path = BASE_DIR / "storage" / "app.db"

    # --- LangGraph checkpointer (kept separate from business DB) ---
    checkpoint_db_path: Path = BASE_DIR / "storage" / "checkpoints.db"

    # --- object storage (Dataset Service must not touch raw local paths) ---
    object_storage_backend: Literal["local", "s3"] = "local"
    dataset_storage_dir: Path = BASE_DIR / "storage" / "datasets"
    output_dir: Path = BASE_DIR / "storage" / "outputs"
    s3_endpoint_url: str = ""
    s3_bucket: str = "dataguard"
    s3_region: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""

    # --- redis (reserved for cache/rate-limit/lock/task-queue later; YAGNI now) ---
    redis_url: str = ""

    # --- LLM (cloud OpenAI-compatible API; fake only for tests/CI/dev) ---
    llm_provider: Literal["fake", "deepseek", "openai", "qwen", "openai_compatible"] = "openai_compatible"
    llm_base_url: str = "https://api.deepseek.com/v1"
    llm_api_key: str = ""
    llm_model: str = "deepseek-chat"
    llm_temperature: float = 0.0
    llm_max_tokens: int = 4096
    llm_timeout_seconds: float = 180.0
    llm_max_retries: int = 2
    # 备用模型（主模型失败自动切换；默认百炼 qwen-turbo，同 Key 可用）
    llm_fallback_model: str = "qwen-turbo"
    llm_fallback_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    llm_fallback_api_key: str = ""

    # --- governance ---
    max_sample_rows: int = 20
    max_iteration: int = 3
    low_risk_auto_execute: bool = True
    medium_risk_mode: Literal["auto", "approval"] = "approval"  # MEDIUM policy

    # --- auth (JWT) ---
    auth_secret: str = "dev-secret-change-me"  # 生产用 DG_AUTH_SECRET 覆盖

    # --- workflow execution ---
    workflow_execution_mode: Literal["background", "sync"] = "background"

    @property
    def business_db_url(self) -> str:
        """Effective business DB URL. Empty DG_DATABASE_URL -> local SQLite."""
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.app_db_path.as_posix()}"


settings = Settings()
