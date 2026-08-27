"""DataGovernanceState: strongly-typed LangGraph state.

Values are stored as plain dicts at the channel level (LangGraph merges
un-annotated keys with last-value-wins semantics), while every value is
validated/typed by Pydantic models in app/schemas.  No bare-dict core state.
"""

from typing import TypedDict


class DataGovernanceState(TypedDict):
    # basics
    run_id: str
    user_request: str
    source_type: str  # file | database | web
    dataset_id: str
    dataset_ext: str  # csv | xlsx | json

    # supervisor routing
    supervisor_route: dict

    # data understanding
    schema_info: dict
    profile_result: dict
    evidence: dict

    # quality problems
    issues: list

    # agent plan
    cleaning_plan: dict
    plan_validation: dict

    # execution & validation
    risk_assessment: dict
    execution_results: list
    cleaned_key: str
    validation_result: dict
    reflection: dict

    # human loop
    approval_status: str
    approval_results: list  # [{id, tool, column, risk, decision}]

    # workflow
    current_node: str
    iteration: int

    # trace
    trace_id: str
