"""LLM 设置 API / 服务测试：脱敏 / 保存读取 / 校验 / 热生效配置读取。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.llm_settings import get_llm_config, mask_api_key, save_llm_config
from app.storage.database import SessionLocal
from app.models import LLMSetting

client = TestClient(app)


@pytest.fixture(autouse=True)
def _cleanup_llm_settings():
    """测试前后清理 llm_settings，避免污染真实运行配置。"""
    yield
    with SessionLocal() as session:
        session.query(LLMSetting).delete()
        session.commit()


def test_mask_api_key():
    assert mask_api_key("") == ""
    assert mask_api_key("sk-abc12345") == "sk-****2345"
    assert mask_api_key("short") == "****"


def test_get_llm_settings_masked(client=client):
    resp = client.get("/api/settings/llm")
    assert resp.status_code == 200
    body = resp.json()
    # api_key 必须脱敏且不返回明文
    assert "api_key" not in body
    assert body.get("model")
    assert body.get("base_url")
    assert body.get("configured") is False  # 测试环境未保存过 → 回退 .env


def test_put_llm_settings_and_readback(client=client):
    resp = client.put(
        "/api/settings/llm",
        json={"provider": "openai_compatible", "model": "qwen-flash", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "api_key": "sk-test123456", "temperature": 0.2, "max_tokens": 2048},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "qwen-flash"
    assert body["api_key_masked"] == "sk-****3456"
    assert "api_key" not in body
    assert body["configured"] is True

    # 重新读取仍是新值
    got = client.get("/api/settings/llm").json()
    assert got["model"] == "qwen-flash"

    # 热生效：get_llm_config 返回 DB 值
    cfg = get_llm_config()
    assert cfg["model"] == "qwen-flash"
    assert cfg["api_key"] == "sk-test123456"


def test_put_llm_settings_blank_key_keeps_old(client=client):
    client.put("/api/settings/llm", json={"model": "qwen-flash", "base_url": "https://x/v1", "api_key": "sk-keepme999"})
    resp = client.put("/api/settings/llm", json={"model": "qwen-max", "base_url": "https://x/v1", "api_key": ""})
    assert resp.status_code == 200
    assert resp.json()["model"] == "qwen-max"
    assert get_llm_config()["api_key"] == "sk-keepme999"  # 空 key 保留旧值


def test_put_llm_settings_validation(client=client):
    # model 空 → 400
    assert client.put("/api/settings/llm", json={"model": "", "base_url": "https://x/v1"}).status_code == 400
    # base_url 空 → 400
    assert client.put("/api/settings/llm", json={"model": "qwen-flash", "base_url": ""}).status_code == 400


def test_llm_test_endpoint_validation(client=client):
    # 未配置 key → 400 提示
    client.put("/api/settings/llm", json={"model": "qwen-flash", "base_url": "https://x/v1", "api_key": ""})
    cfg = get_llm_config()
    if not cfg.get("api_key"):
        resp = client.post("/api/settings/llm/test")
        assert resp.status_code == 400
        assert "API Key" in resp.json()["detail"]
