"""Dataset upload loader tests: CSV / Excel / JSON formats (提示词：支持 CSV、Excel、JSON)."""

from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest

from app.services.dataset_service import DatasetService
from app.tools.data.loader import load_dataframe

DEMO_CSV = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "customer_id": ["10001", "10002", "10003"],
            "name": ["Alice", "Bob", "Cathy"],
            "phone": ["138-1234-5678", "13912345678", "+86 137 1234 5678"],
            "email": ["alice@qq", "bob@gmail.com", None],
        }
    )


def test_upload_csv_loads():
    with open(DEMO_CSV, "rb") as f:
        info = DatasetService().save_upload("customer.csv", f.read())
    df = load_dataframe(info.id, "csv")
    assert len(df) == 504
    assert "phone" in df.columns


def test_upload_xlsx_loads():
    """Excel（.xlsx）上传后可按 xlsx 加载，与 csv 内容一致。"""
    buf = BytesIO()
    _sample_df().to_excel(buf, index=False)
    info = DatasetService().save_upload("sample.xlsx", buf.getvalue())
    assert info.filename == "sample.xlsx"
    assert info.row_count == 3
    df = load_dataframe(info.id, "xlsx")
    assert list(df.columns) == ["customer_id", "name", "phone", "email"]
    assert df.iloc[0]["phone"] == "138-1234-5678"


def test_upload_json_loads():
    """JSON（表格数组）上传后可按 json 加载。"""
    buf = BytesIO(_sample_df().to_json(orient="records").encode("utf-8"))
    info = DatasetService().save_upload("sample.json", buf.getvalue())
    df = load_dataframe(info.id, "json")
    assert df.shape == (3, 4)


def test_upload_unsupported_ext_rejected():
    """不支持的扩展名（如 .txt）应被拒绝，而不是静默按 CSV 解析。"""
    with pytest.raises(ValueError, match="unsupported file type"):
        DatasetService().save_upload("notes.txt", b"hello world")
