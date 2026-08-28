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


def test_dataset_list_has_name_status_and_search(client):
    """数据集列表：返回自定义名 + 最近治理状态 + 问题数；支持 search 模糊筛选。"""
    # 上传两个数据集，一个带自定义名
    with open(DEMO_CSV, "rb") as f:
        r1 = client.post(
            "/api/dataset/upload",
            files={"file": ("customer.csv", f, "text/csv")},
            data={"name": "客户全量测试数据"},
        )
    with open(DEMO_CSV, "rb") as f:
        r2 = client.post(
            "/api/dataset/upload",
            files={"file": ("orders.csv", f, "text/csv")},
        )
    ds1 = r1.json()["dataset_id"]

    # 跑一次治理，产生 run 与 issues
    from app.services.workflow_service import WorkflowService

    WorkflowService().start(ds1, "govern")

    body = client.get("/api/dataset/list?limit=20").json()
    assert body["total"] >= 2
    item = next(d for d in body["datasets"] if d["id"] == ds1)
    assert item["name"] == "客户全量测试数据"  # 自定义名（之前 list 丢失 name 的根因）
    assert item["filename"] == "customer.csv"
    assert item["last_status"] in ("WAITING_APPROVAL", "RUNNING", "SUCCESS", "FAILED")
    assert item["issue_count"] >= 1  # 治理后问题数>0

    # search 按自定义名/文件名模糊过滤
    hit = client.get("/api/dataset/list?search=客户").json()
    assert any(d["name"] == "客户全量测试数据" for d in hit["datasets"])
    miss = client.get("/api/dataset/list?search=不存在xyz").json()
    assert miss["datasets"] == []

    # source_type 筛选
    only_file = client.get("/api/dataset/list?source_type=file").json()
    assert all(d["source_type"] == "file" for d in only_file["datasets"])


def test_dataset_rename_updates_name_everywhere(client):
    """事后改名：PATCH 更新 name，list/issues 立即生效；空名拒绝；不存在 404。"""
    with open(DEMO_CSV, "rb") as f:
        r = client.post(
            "/api/dataset/upload",
            files={"file": ("customer.csv", f, "text/csv")},
        )
    ds_id = r.json()["dataset_id"]

    # 改名
    resp = client.patch(f"/api/dataset/{ds_id}", json={"name": "改名后的数据集"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "改名后的数据集"

    # list 立即生效
    item = next(d for d in client.get("/api/dataset/list?limit=50").json()["datasets"] if d["id"] == ds_id)
    assert item["name"] == "改名后的数据集"

    # 跑一次治理 → issues 的 dataset_name 也显示新名
    client.post("/api/workflow/start", json={"dataset_id": ds_id})
    issues = client.get(f"/api/issues?dataset_id={ds_id}").json().get("issues", [])
    assert issues and all(i["dataset_name"] == "改名后的数据集" for i in issues)

    # 空名 → 400；不存在 → 404
    assert client.patch(f"/api/dataset/{ds_id}", json={"name": "   "}).status_code == 400
    assert client.patch("/api/dataset/ds_not_found_1", json={"name": "x"}).status_code == 404


def test_dataset_delete_cascades(client, auth_headers):
    """删除数据集（需登录）：DB 记录 + 运行历史级联删除；list/issues 消失；不存在 404。"""
    with open(DEMO_CSV, "rb") as f:
        r = client.post(
            "/api/dataset/upload",
            files={"file": ("customer.csv", f, "text/csv")},
            data={"name": "待删除数据集"},
        )
    ds_id = r.json()["dataset_id"]

    # 跑一次治理产生 issues/runs
    client.post("/api/workflow/start", json={"dataset_id": ds_id})
    assert client.get(f"/api/issues?dataset_id={ds_id}").json().get("issues")  # 治理后有 issues

    # 未登录删除 → 401
    assert client.delete(f"/api/dataset/{ds_id}").status_code == 401

    # 登录后删除
    resp = client.delete(f"/api/dataset/{ds_id}", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # list/issues 都不再包含该数据集
    all_ds = client.get("/api/dataset/list?limit=50").json()["datasets"]
    assert all(d["id"] != ds_id for d in all_ds)
    assert client.get(f"/api/issues?dataset_id={ds_id}").json().get("issues") == []

    # 重复删除 → 404（需登录）
    assert client.delete(f"/api/dataset/{ds_id}", headers=auth_headers).status_code == 404
