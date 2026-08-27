"""Cleaning tools: LOW-risk deterministic normalizers.

Cleaning tools transform DataFrames via `apply(df, column, **params)` and are
only invoked by the Execution Engine — never by agents.
"""

import re

import pandas as pd

from app.schemas.common import RiskLevel
from app.tools.base import BaseTool, CleaningOutput

_DIGITS = re.compile(r"\D")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PHONE_OK = re.compile(r"^1[3-9]\d{9}$")


def _str_value(v) -> str:
    return str(v).strip()


def _normalize_phone_value(v):
    if pd.isna(v):
        return v, False
    s = _str_value(v)
    if not s:
        return v, False
    digits = _DIGITS.sub("", s)
    if len(digits) == 13 and digits.startswith("86"):
        digits = digits[2:]
    if _PHONE_OK.match(digits):
        return digits, digits != s
    return v, False  # unparseable -> unchanged


def _normalize_email_value(v):
    if pd.isna(v):
        return v, False
    s = _str_value(v).lower()
    if not s:
        return v, False
    if _EMAIL_RE.match(s):
        return s, s != _str_value(v)
    return v, False


def _normalize_date_value(v):
    if pd.isna(v):
        return v, False
    s = _str_value(v)
    if not s:
        return v, False
    try:
        dt = pd.to_datetime(s, format="mixed", errors="raise")
        out = dt.strftime("%Y-%m-%d")
        return out, out != s
    except Exception:
        return v, False


class NormalizePhoneTool(BaseTool):
    name = "normalize_phone"
    description = "Normalize Chinese mobile phone numbers to canonical 11-digit form"
    risk_level = RiskLevel.LOW

    def apply(self, df: pd.DataFrame, column: str, **params) -> tuple[pd.DataFrame, CleaningOutput]:
        values = df[column].tolist()
        new_values: list = []
        changed = 0
        samples: list[dict] = []
        for v in values:
            nv, ch = _normalize_phone_value(v)
            new_values.append(nv)
            if ch:
                changed += 1
                if len(samples) < 5:
                    samples.append({"before": v, "after": nv})
        new_df = df.copy()
        new_df[column] = new_values
        return new_df, CleaningOutput(affected_rows=changed, samples=samples)

    def execute(self, **params) -> dict:
        raise NotImplementedError("cleaning tools run via Execution Engine apply()")


class NormalizeEmailTool(BaseTool):
    name = "normalize_email"
    description = "Lowercase and validate email addresses"
    risk_level = RiskLevel.LOW

    def apply(self, df: pd.DataFrame, column: str, **params) -> tuple[pd.DataFrame, CleaningOutput]:
        values = df[column].tolist()
        new_values: list = []
        changed = 0
        samples: list[dict] = []
        for v in values:
            nv, ch = _normalize_email_value(v)
            new_values.append(nv)
            if ch:
                changed += 1
                if len(samples) < 5:
                    samples.append({"before": v, "after": nv})
        new_df = df.copy()
        new_df[column] = new_values
        return new_df, CleaningOutput(affected_rows=changed, samples=samples)

    def execute(self, **params) -> dict:
        raise NotImplementedError("cleaning tools run via Execution Engine apply()")


class NormalizeDateTool(BaseTool):
    name = "normalize_date"
    description = "Normalize date values to ISO yyyy-mm-dd"
    risk_level = RiskLevel.LOW

    def apply(self, df: pd.DataFrame, column: str, **params) -> tuple[pd.DataFrame, CleaningOutput]:
        values = df[column].tolist()
        new_values: list = []
        changed = 0
        samples: list[dict] = []
        for v in values:
            nv, ch = _normalize_date_value(v)
            new_values.append(nv)
            if ch:
                changed += 1
                if len(samples) < 5:
                    samples.append({"before": v, "after": nv})
        new_df = df.copy()
        new_df[column] = new_values
        return new_df, CleaningOutput(affected_rows=changed, samples=samples)

    def execute(self, **params) -> dict:
        raise NotImplementedError("cleaning tools run via Execution Engine apply()")


class TrimWhitespaceTool(BaseTool):
    name = "trim_whitespace"
    description = "Trim leading/trailing whitespace in string cells"
    risk_level = RiskLevel.LOW

    def apply(self, df: pd.DataFrame, column: str, **params) -> tuple[pd.DataFrame, CleaningOutput]:
        s = df[column]
        mask = s.map(lambda v: isinstance(v, str) and v.strip() != v)
        changed = int(mask.sum())
        samples = []
        if changed:
            for i in df.index[mask].tolist()[:5]:
                samples.append({"before": df.at[i, column], "after": df.at[i, column].strip()})
            new_df = df.copy()
            new_df.loc[mask, column] = s[mask].map(lambda v: v.strip())
        else:
            new_df = df.copy()
        return new_df, CleaningOutput(affected_rows=changed, samples=samples)

    def execute(self, **params) -> dict:
        raise NotImplementedError("cleaning tools run via Execution Engine apply()")
