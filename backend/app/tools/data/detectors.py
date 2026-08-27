"""Deterministic data quality detectors (pure Python, no LLM).

Each detector returns a JSON-serializable dict with count/samples so it can
feed both the Evidence Builder and the Tool Registry.
"""

import re

import pandas as pd

_NUM = re.compile(r"[0-9]")
_ALPHA = re.compile(r"[A-Za-z]")


def _missing_mask(df: pd.DataFrame, column: str) -> pd.Series:
    s = df[column]
    return s.isna() | (s.astype(str).str.strip() == "")


def detect_missing(df: pd.DataFrame, column: str) -> dict:
    mask = _missing_mask(df, column)
    count = int(mask.sum())
    samples = df.loc[mask, column].head(5).tolist()
    return {"column": column, "anomaly_type": "missing", "count": count, "samples": samples}


def detect_duplicate(df: pd.DataFrame, column: str) -> dict:
    counts = df[column].value_counts(dropna=False)
    dup = counts[counts > 1]
    count = int((df[column].map(dup) > 1).sum()) if len(dup) else 0
    samples = [{"value": v, "occurrences": int(c)} for v, c in dup.head(5).items()]
    return {"column": column, "anomaly_type": "duplicate", "count": count, "samples": samples}


def _pattern(v) -> str:
    s = _ALPHA.sub("A", _NUM.sub("N", str(v)))
    return s[:20]


def detect_pattern(df: pd.DataFrame, column: str) -> dict:
    """Character-class pattern distribution for string columns (format detection)."""
    s = df[column].dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return {"column": column, "anomaly_type": "pattern", "count": 0, "samples": []}
    pat = s.map(_pattern)
    distribution = pat.value_counts().head(8).to_dict()
    top_pattern, top_count = distribution.popitem() if distribution else (None, 0)
    total = int(len(s))
    dominant_ratio = top_count / total if total else 0.0
    return {
        "column": column,
        "anomaly_type": "pattern",
        "count": int(total - top_count) if distribution else 0,
        "dominant_pattern": top_pattern,
        "dominant_ratio": round(dominant_ratio, 3),
        "distribution": {k: int(v) for k, v in distribution.items()},
        "samples": s.head(5).tolist(),
    }


def detect_outlier(df: pd.DataFrame, column: str) -> dict:
    """IQR-based outlier detection for numeric columns."""
    s = pd.to_numeric(df[column], errors="coerce").dropna()
    if s.empty or s.nunique() <= 2:
        return {"column": column, "anomaly_type": "outlier", "count": 0, "samples": []}
    q1, q3 = s.quantile(0.25), s.quantile(0.75)
    iqr = q3 - q1
    if iqr == 0:
        return {"column": column, "anomaly_type": "outlier", "count": 0, "samples": []}
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = s[(s < lo) | (s > hi)]
    return {
        "column": column,
        "anomaly_type": "outlier",
        "count": int(len(outliers)),
        "samples": outliers.head(5).astype(float).tolist(),
    }
