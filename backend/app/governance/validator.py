"""Quality Validator — deterministic before/after scoring (no LLM).

Scores 0-100 across completeness / uniqueness / format_validity.
"""

import re

import pandas as pd

from app.schemas.validation import QualityScore, ValidationResult

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_RE = re.compile(r"^1[3-9]\d{9}$")


def _is_date(v) -> bool:
    try:
        pd.to_datetime(v, format="mixed", errors="raise")
        return True
    except Exception:
        return False


def _column_format_validity(df: pd.DataFrame, column: str) -> float:
    col = str(column).lower()
    s = df[column].dropna().astype(str).str.strip()
    s = s[s != ""]
    if s.empty:
        return 1.0
    if "phone" in col:
        valid = s.str.match(_PHONE_RE)
    elif "email" in col:
        valid = s.str.match(_EMAIL_RE)
    elif "date" in col or "time" in col:
        valid = s.map(_is_date)
    else:
        return 1.0
    return float(valid.mean())


def compute_quality(df: pd.DataFrame) -> QualityScore:
    if df.empty:
        return QualityScore(overall=0.0, dimensions={})

    n_cols = max(df.shape[1], 1)
    total = len(df)

    # completeness: 1 - null ratio (empty strings count as missing)
    completeness_scores = []
    uniqueness_scores = []
    format_scores = []
    for column in df.columns:
        s = df[column]
        null_mask = s.isna() | (s.astype(str).str.strip() == "")
        completeness_scores.append(1.0 - float(null_mask.mean()))

        non_null = s[~null_mask]
        if len(non_null) <= 1:
            uniqueness_scores.append(1.0)
        else:
            dup_ratio = 1.0 - non_null.nunique() / len(non_null)
            uniqueness_scores.append(1.0 - dup_ratio)

        format_scores.append(_column_format_validity(df, column))

    completeness = sum(completeness_scores) / n_cols
    uniqueness = sum(uniqueness_scores) / n_cols
    format_validity = sum(format_scores) / n_cols

    overall = 100.0 * (0.4 * completeness + 0.3 * uniqueness + 0.3 * format_validity)
    return QualityScore(
        overall=round(overall, 2),
        dimensions={
            "completeness": round(completeness, 4),
            "uniqueness": round(uniqueness, 4),
            "format_validity": round(format_validity, 4),
        },
    )


class QualityValidator:
    """Compares quality before vs after cleaning."""

    def validate(self, *, before_df: pd.DataFrame, after_df: pd.DataFrame) -> ValidationResult:
        before = compute_quality(before_df)
        after = compute_quality(after_df)
        passed = after.overall >= before.overall
        details = [
            f"overall: {before.overall:.1f} -> {after.overall:.1f}",
        ]
        for dim in ("completeness", "uniqueness", "format_validity"):
            b = before.dimensions.get(dim, 0.0)
            a = after.dimensions.get(dim, 0.0)
            details.append(f"{dim}: {b:.3f} -> {a:.3f}")
        return ValidationResult(
            status="PASS" if passed else "FAIL",
            quality_before=before,
            quality_after=after,
            details=details,
        )
