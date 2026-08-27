"""Unit tests: Python Data Profiler + quality validator."""

import pandas as pd

from app.governance.validator import QualityValidator, compute_quality
from app.tools.data.profiler import profile_dataframe


def _dirty_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["C0001", "C0002", "C0001", "C0004"],  # duplicate C0001
            "phone": ["138-1234-5678", "13812345678", "13900000000", "12345"],
            "email": ["a@qq", "b@example.com", "c@example.com", None],
            "age": [30, 45, -5, 60],
            "register_date": ["2023-01-05", "2023/01/05", "2023-01-05", "2023-01-05"],
        }
    )


def _clean_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["C0001", "C0002", "C0003", "C0004"],
            "phone": ["13812345678", "13812345678", "13900000000", "13700000000"],
            "email": ["a@qq.com", "b@example.com", "c@example.com", "d@example.com"],
            "age": [30, 45, 25, 60],
            "register_date": ["2023-01-05", "2023-01-05", "2023-01-05", "2023-01-05"],
        }
    )


def test_profile_structure():
    profile = profile_dataframe(_dirty_df())
    assert profile["rows"] == 4
    assert profile["columns"] == 5
    assert "phone" in profile["schema"]
    assert profile["schema"]["phone"]["dtype"] == "string"
    assert profile["anomalies"]  # deterministic anomaly candidates present


def test_profile_detects_duplicate_and_missing():
    profile = profile_dataframe(_dirty_df())
    assert any(a["anomaly_type"] == "duplicate" for a in profile["anomalies"]["customer_id"])
    assert any(a["anomaly_type"] == "missing" for a in profile["anomalies"]["email"])


def test_quality_score_clean_beats_dirty():
    dirty = compute_quality(_dirty_df())
    clean = compute_quality(_clean_df())
    assert clean.overall > dirty.overall
    assert clean.dimensions["completeness"] > dirty.dimensions["completeness"]


def test_quality_validator_pass():
    result = QualityValidator().validate(before_df=_dirty_df(), after_df=_clean_df())
    assert result.status == "PASS"
    assert result.quality_after.overall > result.quality_before.overall
