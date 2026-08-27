"""Shared enums and value types."""

from enum import Enum


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SourceType(str, Enum):
    FILE = "file"
    WEB = "web"
    DATABASE = "database"


class ApprovalStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ExecutionMode(str, Enum):
    DRY_RUN = "DRY_RUN"
    EXECUTE = "EXECUTE"


class EventType(str, Enum):
    """Fixed trace event types (Part 3, section 44)."""

    WORKFLOW_START = "WORKFLOW_START"
    AGENT_START = "AGENT_START"
    AGENT_DECISION = "AGENT_DECISION"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESULT = "TOOL_RESULT"
    STATE_CHANGE = "STATE_CHANGE"
    HUMAN_APPROVAL = "HUMAN_APPROVAL"
    VALIDATION = "VALIDATION"
    ERROR = "ERROR"
    WORKFLOW_END = "WORKFLOW_END"
