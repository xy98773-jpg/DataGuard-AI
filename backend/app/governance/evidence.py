"""Evidence Builder — controls how much data reaches the LLM.

The full dataset must NEVER be passed to the model. This builder compresses
the deterministic profile + limited samples into the LLM context.
"""

import pandas as pd

from app.config import settings
from app.schemas.dataset import DatasetProfile
from app.schemas.evidence import Evidence
from app.tools.data.loader import load_dataframe


def build_evidence(
    dataset_id: str,
    profile: DatasetProfile,
    ext: str = "csv",
    source_type: str = "file",
    max_sample_rows: int | None = None,
) -> Evidence:
    max_rows = max_sample_rows or settings.max_sample_rows
    schema_summary = {
        col: {k: v for k, v in p.model_dump().items() if k != "sample_values"}
        for col, p in profile.schema.items()
    }
    if source_type == "database":
        from app.tools.data.loader import load_database_dataframe

        df = load_database_dataframe(dataset_id, max_rows)
    else:
        from app.tools.data.loader import load_dataframe

        df = load_dataframe(dataset_id, ext)
    sample_rows = df.head(max_rows).to_dict("records")
    return Evidence(
        rows=profile.rows,
        columns=profile.columns,
        schema_summary=schema_summary,
        statistics=profile.statistics,
        sample_rows=sample_rows,
        candidate_anomalies=profile.anomalies,
    )
