"""MEDIUM/HIGH-risk cleaning tools (Phase 4).

- fill_missing      (MEDIUM): fill missing/empty cells with a value or mode
- delete_duplicate  (HIGH):   drop duplicate rows by column, keep first

Both run via Execution Engine apply() — never called by agents directly.
"""

import pandas as pd

from app.schemas.common import RiskLevel
from app.tools.base import BaseTool, CleaningOutput


class FillMissingTool(BaseTool):
    name = "fill_missing"
    description = "Fill missing/empty values in a column (with fill_value or column mode)"
    risk_level = RiskLevel.MEDIUM

    def apply(self, df: pd.DataFrame, column: str, **params) -> tuple[pd.DataFrame, CleaningOutput]:
        fill_value = params.get("fill_value")
        s = df[column]
        mask = s.isna() | (s.astype(str).str.strip() == "")
        changed = int(mask.sum())
        samples = []
        if changed:
            value = fill_value
            if value is None:
                non_null = s[~mask]
                value = non_null.mode().iloc[0] if not non_null.mode().empty else ""
            new_df = df.copy()
            new_df.loc[mask, column] = value
            for i in df.index[mask].tolist()[:5]:
                samples.append({"before": df.at[i, column], "after": value})
        else:
            new_df = df.copy()
        return new_df, CleaningOutput(affected_rows=changed, samples=samples)

    def execute(self, **params) -> dict:
        raise NotImplementedError("cleaning tools run via Execution Engine apply()")


class DeleteDuplicateTool(BaseTool):
    name = "delete_duplicate"
    description = "Delete duplicate rows by column (keep first occurrence)"
    risk_level = RiskLevel.HIGH

    def apply(self, df: pd.DataFrame, column: str, **params) -> tuple[pd.DataFrame, CleaningOutput]:
        keep = params.get("keep", "first")
        counts = df[column].value_counts(dropna=False)
        dup_counts = counts[counts > 1]
        # rows to delete = total duplicate-group rows minus the kept first of each group
        changed = int(sum(c - 1 for c in dup_counts.values))
        samples = [
            {"before": {"column_value": v, "occurrences": int(c)}, "after": "deleted"}
            for v, c in list(dup_counts.items())[:5]
        ]
        new_df = df.drop_duplicates(subset=[column], keep=keep)
        return new_df, CleaningOutput(affected_rows=changed, samples=samples)

    def execute(self, **params) -> dict:
        raise NotImplementedError("cleaning tools run via Execution Engine apply()")
