"""Python Data Profiler — deterministic statistics & anomaly candidates.

No LLM here. The Profiler Agent later interprets THIS output.
"""

from typing import Any

import pandas as pd

from app.tools.data import detectors


def _dtype_label(dtype) -> str:
    name = str(dtype)
    if name.startswith("int") or name.startswith("float"):
        return "numeric"
    # pandas 2.x -> "object"; pandas 3.x (Arrow-backed) -> "str"
    if name == "object" or name == "str" or name == "string":
        return "string"
    if name.startswith("datetime"):
        return "datetime"
    return name


def _string_pattern_distribution(s: pd.Series) -> dict[str, int]:
    s = s.dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return {}
    return s.map(detectors._pattern).value_counts().head(5).to_dict()


def profile_dataframe(df: pd.DataFrame) -> dict[str, Any]:
    """Produce DatasetProfile dict: schema + statistics + patterns + anomalies."""
    rows, cols = int(len(df)), int(df.shape[1])
    schema: dict[str, dict[str, Any]] = {}
    statistics: dict[str, dict[str, Any]] = {}
    patterns: dict[str, dict[str, int]] = {}
    anomalies: dict[str, list[dict[str, Any]]] = {}

    for column in df.columns:
        s = df[column]
        dtype = _dtype_label(s.dtype)
        total = len(s)
        null_count = int(s.isna().sum())
        null_rate = round(null_count / total, 4) if total else 0.0
        non_null = s.dropna()
        unique_rate = round(non_null.nunique() / total, 4) if total else 0.0
        samples = s.head(5).tolist()

        col_profile: dict[str, Any] = {
            "name": str(column),
            "dtype": dtype,
            "null_rate": null_rate,
            "unique_rate": unique_rate,
            "sample_values": samples,
        }

        if dtype == "numeric":
            num = pd.to_numeric(s, errors="coerce").dropna()
            if not num.empty:
                col_profile.update(
                    min=float(num.min()),
                    max=float(num.max()),
                    mean=round(float(num.mean()), 4),
                )
                statistics[str(column)] = {
                    "min": col_profile["min"],
                    "max": col_profile["max"],
                    "mean": col_profile["mean"],
                    "std": round(float(num.std()), 4) if len(num) > 1 else 0.0,
                    "median": float(num.median()),
                }
        elif dtype == "string":
            pat = _string_pattern_distribution(s)
            if pat:
                col_profile["patterns"] = pat
                patterns[str(column)] = pat

        schema[str(column)] = col_profile

    # anomaly candidates (deterministic)
    for column in df.columns:
        col_anomalies: list[dict[str, Any]] = []
        s = df[column]
        if _dtype_label(s.dtype) in ("string", "object"):
            missing = detectors.detect_missing(df, column)
            dup = detectors.detect_duplicate(df, column)
            pat = detectors.detect_pattern(df, column)
            for det in (missing, dup, pat):
                if det["count"] > 0:
                    col_anomalies.append({k: v for k, v in det.items() if k != "column"})
        else:
            missing = detectors.detect_missing(df, column)
            outlier = detectors.detect_outlier(df, column)
            for det in (missing, outlier):
                if det["count"] > 0:
                    col_anomalies.append({k: v for k, v in det.items() if k != "column"})
        if col_anomalies:
            anomalies[str(column)] = col_anomalies

    return {
        "rows": rows,
        "columns": cols,
        "schema": schema,
        "statistics": statistics,
        "patterns": patterns,
        "anomalies": anomalies,
    }
