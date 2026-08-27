"""Data analysis tools: profile_dataset + detect_* (read-only)."""

from app.schemas.common import RiskLevel
from app.tools.base import BaseTool
from app.tools.data import detectors  # noqa: F401
from app.tools.data.loader import load_database_dataframe, load_dataframe
from app.tools.data.profiler import profile_dataframe
from app.tools.registry import get_registry


class ProfileDatasetTool(BaseTool):
    name = "profile_dataset"
    description = "Run the deterministic Python Data Profiler on a dataset (schema/statistics/patterns/anomalies)"
    risk_level = RiskLevel.LOW

    def execute(self, dataset_id: str, ext: str = "csv", source_type: str = "file", **params) -> dict:
        if source_type == "database":
            df = load_database_dataframe(dataset_id)
        else:
            df = load_dataframe(dataset_id, ext)
        return profile_dataframe(df)


class DetectMissingTool(BaseTool):
    name = "detect_missing"
    description = "Detect missing/empty values in a column"
    risk_level = RiskLevel.LOW

    def execute(self, dataset_id: str, column: str, ext: str = "csv", **params) -> dict:
        df = load_dataframe(dataset_id, ext)
        return detectors.detect_missing(df, column)


class DetectDuplicateTool(BaseTool):
    name = "detect_duplicate"
    description = "Detect duplicate values in a column"
    risk_level = RiskLevel.LOW

    def execute(self, dataset_id: str, column: str, ext: str = "csv", **params) -> dict:
        df = load_dataframe(dataset_id, ext)
        return detectors.detect_duplicate(df, column)


class DetectPatternTool(BaseTool):
    name = "detect_pattern"
    description = "Detect format patterns in a string column"
    risk_level = RiskLevel.LOW

    def execute(self, dataset_id: str, column: str, ext: str = "csv", **params) -> dict:
        df = load_dataframe(dataset_id, ext)
        return detectors.detect_pattern(df, column)


class DetectOutlierTool(BaseTool):
    name = "detect_outlier"
    description = "Detect numeric outliers (IQR) in a column"
    risk_level = RiskLevel.LOW

    def execute(self, dataset_id: str, column: str, ext: str = "csv", **params) -> dict:
        df = load_dataframe(dataset_id, ext)
        return detectors.detect_outlier(df, column)


_DATA_TOOLS = [
    ProfileDatasetTool(),
    DetectMissingTool(),
    DetectDuplicateTool(),
    DetectPatternTool(),
    DetectOutlierTool(),
]


def register_data_tools() -> None:
    reg = get_registry()
    for tool in _DATA_TOOLS:
        reg.register(tool)
