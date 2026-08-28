"""ORM models for the business SQLite DB (app.db).

Schema follows the design spec (Part 3, section 33):
datasets / workflow_runs / dataset_profiles / issues / cleaning_plans /
executions / validations / trace_events / approvals.
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.database import Base


def gen_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("ds"))
    filename: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, default="")  # 数据集显示名（网页上展示的名称）
    source_type: Mapped[str] = mapped_column(String, default="file")  # file | web | database
    storage_path: Mapped[str] = mapped_column(String, default="")
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    column_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkflowRun(Base):
    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("run"))
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    goal: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="PENDING")  # PENDING/RUNNING/WAITING_APPROVAL/SUCCESS/FAILED
    current_node: Mapped[str] = mapped_column(String, default="")
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    trace_id: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DatasetProfile(Base):
    __tablename__ = "dataset_profiles"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("prof"))
    dataset_id: Mapped[str] = mapped_column(String, ForeignKey("datasets.id"), nullable=False)
    schema: Mapped[dict] = mapped_column(JSON, default=dict)
    statistics: Mapped[dict] = mapped_column(JSON, default=dict)
    patterns: Mapped[dict] = mapped_column(JSON, default=dict)


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("issue"))
    agent_issue_id: Mapped[str] = mapped_column(String, default="")  # e.g. ISSUE001
    run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
    issue_type: Mapped[str] = mapped_column(String, default="")
    column_name: Mapped[str] = mapped_column(String, default="")
    severity: Mapped[str] = mapped_column(String, default="")  # LOW/MEDIUM/HIGH
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    affected_rows: Mapped[int] = mapped_column(Integer, default=0)
    evidence: Mapped[list] = mapped_column(JSON, default=list)


class CleaningPlan(Base):
    __tablename__ = "cleaning_plans"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("plan"))
    run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[str] = mapped_column(String, default="LOW")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("exe"))
    run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
    tool_name: Mapped[str] = mapped_column(String, default="")
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String, default="")
    latency: Mapped[float] = mapped_column(Float, default=0.0)


class Validation(Base):
    __tablename__ = "validations"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("val"))
    run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
    before_score: Mapped[float] = mapped_column(Float, default=0.0)
    after_score: Mapped[float] = mapped_column(Float, default=0.0)
    result: Mapped[str] = mapped_column(String, default="")  # PASS/FAIL
    details: Mapped[list] = mapped_column(JSON, default=list)


class TraceEvent(Base):
    __tablename__ = "trace_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
    node: Mapped[str] = mapped_column(String, default="")
    event_type: Mapped[str] = mapped_column(String, default="")
    input: Mapped[dict] = mapped_column(JSON, default=dict)
    output: Mapped[dict] = mapped_column(JSON, default=dict)
    latency: Mapped[float] = mapped_column(Float, default=0.0)
    tokens: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Approval(Base):
    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("appr"))
    run_id: Mapped[str] = mapped_column(String, ForeignKey("workflow_runs.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String, default="")
    status: Mapped[str] = mapped_column(String, default="PENDING")  # PENDING/APPROVED/REJECTED
    operator: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LLMSetting(Base):
    """LLM 运行时配置（UI 可视化配置，热生效；未配置时回退 .env 默认）。

    单行记录（id="default"）：页面保存后立即生效，无需重启后端。
    api_key 只存明文于本地业务库，接口返回时一律脱敏。
    fallback_*：备用模型（主模型失败自动切换，鲁棒性设计）。
    """

    __tablename__ = "llm_settings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    provider: Mapped[str] = mapped_column(String, default="openai_compatible")
    model: Mapped[str] = mapped_column(String, default="")
    api_key: Mapped[str] = mapped_column(String, default="")
    base_url: Mapped[str] = mapped_column(String, default="")
    temperature: Mapped[float] = mapped_column(Float, default=0.0)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    fallback_model: Mapped[str] = mapped_column(String, default="")
    fallback_base_url: Mapped[str] = mapped_column(String, default="")
    fallback_api_key: Mapped[str] = mapped_column(String, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class User(Base):
    """平台用户（登录认证用；JWT 无状态鉴权）。

    默认初始化一个管理员账号（admin / 见 README），登录后才能执行
    删除数据集、修改 LLM 配置等敏感写操作（接口层鉴权）。
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: gen_id("user"))
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Integer, default=1)  # 目前单管理员
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
