"""DataFrame loader for tools.

Tools read source files through ObjectStorage (never raw local paths),
then parse with pandas based on file extension.
"""

from functools import lru_cache
from io import BytesIO

import pandas as pd

from app.storage.object_store import get_object_storage


def dataset_file_key(dataset_id: str, ext: str) -> str:
    return f"datasets/{dataset_id}/original.{ext}"


def load_dataframe(dataset_id: str, ext: str = "csv") -> pd.DataFrame:
    storage = get_object_storage()
    key = dataset_file_key(dataset_id, ext)
    if not storage.exists(key):
        raise FileNotFoundError(f"dataset file not found in object storage: {key}")
    data = storage.load(key)
    ext = ext.lower()
    if ext == "csv":
        return pd.read_csv(BytesIO(data))
    if ext in ("xlsx", "xls"):
        return pd.read_excel(BytesIO(data))
    if ext == "json":
        return pd.read_json(BytesIO(data))
    raise ValueError(f"unsupported file extension: {ext}")


def load_database_dataframe(dataset_id: str, limit: int | None = None) -> pd.DataFrame:
    """Load a database-backed dataset as a DataFrame (READ ONLY sample)."""
    from app.services.database_service import DatabaseConnector
    from app.services.dataset_service import DatasetService

    source = DatasetService().get_database_source(dataset_id)
    if source is None:
        raise ValueError(f"dataset {dataset_id} is not a database source")
    connector = DatabaseConnector(**source["connection"])
    return connector.fetch_table_dataframe(source["table"], limit)
