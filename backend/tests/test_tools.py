"""Unit tests: cleaning tools."""

import pandas as pd

from app.tools.cleaning.normalizers import (
    NormalizeDateTool,
    NormalizeEmailTool,
    NormalizePhoneTool,
    TrimWhitespaceTool,
)


def test_phone_normalizer():
    tool = NormalizePhoneTool()
    df = pd.DataFrame({"phone": ["138-1234-5678", "+86 13812345678", "13812345678", "12345", None]})
    new_df, out = tool.apply(df, "phone")
    assert out.affected_rows == 2
    assert new_df["phone"].tolist()[:3] == ["13812345678", "13812345678", "13812345678"]
    assert new_df["phone"].tolist()[3] == "12345"  # invalid unchanged
    assert new_df["phone"].isna().sum() == 1  # missing preserved


def test_email_normalizer():
    tool = NormalizeEmailTool()
    df = pd.DataFrame({"email": [" Test@Gmail.com ", "abc@qq", "ok@example.com", ""]})
    new_df, out = tool.apply(df, "email")
    assert out.affected_rows == 1
    assert new_df["email"].tolist()[0] == "test@gmail.com"
    assert new_df["email"].tolist()[1] == "abc@qq"  # invalid unchanged


def test_date_normalizer():
    tool = NormalizeDateTool()
    df = pd.DataFrame({"register_date": ["2023/01/05", "2023-01-05", "not-a-date"]})
    new_df, out = tool.apply(df, "register_date")
    assert out.affected_rows == 1
    assert new_df["register_date"].tolist()[0] == "2023-01-05"
    assert new_df["register_date"].tolist()[2] == "not-a-date"


def test_trim_whitespace():
    tool = TrimWhitespaceTool()
    df = pd.DataFrame({"name": [" 张三 ", "李四", "  王五"]})
    new_df, out = tool.apply(df, "name")
    assert out.affected_rows == 2
    assert new_df["name"].tolist() == ["张三", "李四", "王五"]
