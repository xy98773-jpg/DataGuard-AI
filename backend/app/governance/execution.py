"""Execution Engine — the ONLY place that applies cleaning tools.

Not an Agent. Flow: Cleaning Plan -> Risk passed -> Execution Engine ->
Tool Registry -> Tool -> Result.

Supports ExecutionMode.DRY_RUN (preview, no writes) and EXECUTE (real run).
"""

from loguru import logger

import pandas as pd

from app.config import settings
from app.schemas.common import ExecutionMode
from app.schemas.plan import CleaningPlan
from app.schemas.tool import ToolResult
from app.storage.object_store import get_object_storage
from app.tools.base import CleaningOutput
from app.tools.data.loader import load_dataframe
from app.tools.registry import get_registry
from app.utils.serialization import json_safe


class ExecutionEngine:
    def __init__(self) -> None:
        self._registry = get_registry()

    def execute_plan(
        self,
        *,
        dataset_id: str,
        plan: CleaningPlan,
        ext: str = "csv",
        source_type: str = "file",
        mode: ExecutionMode = ExecutionMode.EXECUTE,
        mode_by_action: dict[str, ExecutionMode] | None = None,
        run_suffix: str = "",
    ) -> dict:
        if source_type == "database":
            from app.tools.data.loader import load_database_dataframe
            from app.services.dataset_service import DatasetService

            df = load_database_dataframe(dataset_id)
            db_source = DatasetService().get_database_source(dataset_id)
            # Phase 5 Shadow Table 策略：database 源默认只读预览（DRY_RUN）；
            # 只有审批通过（EXECUTE）才写入影子表，绝不覆盖生产表。
        else:
            df = load_dataframe(dataset_id, ext)
            db_source = None
        results: list[dict] = []
        working = df

        for action in plan.actions:
            action_mode = mode
            if mode_by_action and action.tool in mode_by_action:
                action_mode = mode_by_action[action.tool]

            tool = self._registry.get(action.tool)
            if tool is None:
                results.append(self._failed(action, f"tool not registered: {action.tool}"))
                continue
            if not hasattr(tool, "apply"):
                results.append(self._failed(action, "tool does not support dataframe apply()"))
                continue
            # 硬性安全规则：数值列（int/float）禁止 delete_duplicate —— 数值列的
            # 重复值通常是正常分布（年龄/百分比/金额），删除会误删正常数据。
            # 不依赖 LLM 自觉，在 Execution Engine 层最终拦截。
            if action.tool == "delete_duplicate" and action.column in working.columns:
                try:
                    if pd.api.types.is_numeric_dtype(working[action.column]):
                        results.append(
                            self._failed(action, "数值列禁止 delete_duplicate（硬性安全规则）")
                        )
                        continue
                except (TypeError, ValueError):
                    pass
            try:
                new_df, cleaning_output = tool.apply(working, action.column, **action.parameters)
                affected = cleaning_output.affected_rows
                if action_mode == ExecutionMode.EXECUTE:
                    working = new_df
                results.append(
                    {
                        "tool": action.tool,
                        "column": action.column,
                        "status": "success",
                        "affected_rows": int(affected),
                        "samples": json_safe(cleaning_output.samples),
                        "mode": action_mode.value,
                    }
                )
                logger.info(f"[execution] {action.tool}({action.column}) affected={affected} mode={action_mode.value}")
            except Exception as exc:  # noqa: BLE001 - tool failures must be traced
                results.append(self._failed(action, str(exc)))

        cleaned_key = ""
        executed_any = any(
            r.get("mode") == ExecutionMode.EXECUTE.value and r.get("status") == "success" for r in results
        )
        if executed_any:
            if db_source is not None:
                # Shadow Table：清洗结果写入 {table}_agent_{suffix}，生产表保持不变
                from app.services.database_service import DatabaseConnector

                connector = DatabaseConnector(**db_source["connection"])
                shadow = connector.write_shadow_table(
                    working, db_source["table"], run_suffix or "run"
                )
                cleaned_key = f"shadow:{shadow['shadow_table']}"
                results.append(
                    {
                        "tool": "shadow_table",
                        "column": db_source["table"],
                        "status": "success",
                        "affected_rows": int(shadow["rows"]),
                        "samples": [],
                        "mode": "EXECUTE",
                        "shadow_table": shadow["shadow_table"],
                    }
                )
                logger.info(f"[execution] shadow table written: {shadow['shadow_table']} ({shadow['rows']} rows)")
            else:
                cleaned_key = self._save_cleaned(dataset_id, working, ext)

        return {
            "mode": mode.value,
            "results": results,
            "rows_before": int(len(df)),
            "rows_after": int(len(working)),
            "cleaned_key": cleaned_key,
        }

    @staticmethod
    def _failed(action, error: str) -> dict:
        return {
            "tool": action.tool,
            "column": action.column,
            "status": "failed",
            "affected_rows": 0,
            "samples": [],
            "mode": "",
            "error": error,
        }

    @staticmethod
    def _save_cleaned(dataset_id: str, df, ext: str) -> str:
        key = f"outputs/{dataset_id}/cleaned.{ext}"
        if ext == "csv":
            data = df.to_csv(index=False).encode("utf-8-sig")
        elif ext in ("xlsx", "xls"):
            raise NotImplementedError("xlsx output not implemented yet")
        else:
            data = df.to_json(orient="records", force_ascii=False).encode("utf-8")
        storage = get_object_storage()
        storage.save(key, data)
        return key
