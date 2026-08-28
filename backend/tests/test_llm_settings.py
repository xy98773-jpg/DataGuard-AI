"""LLM 设置 API / 服务测试：脱敏 / 保存读取 / 校验 / 热生效 / 认证保护。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import LLMSetting
from app.services.llm_settings import get_llm_config, mask_api_key
from app.storage.database import SessionLocal

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


def test_get_llm_settings_masked(client):
    resp = client.get("/api/settings/llm")
    assert resp.status_code == 200
    body = resp.json()
    # api_key 必须脱敏且不返回明文
    assert "api_key" not in body
    assert body.get("model")
    assert body.get("base_url")
    assert body.get("configured") is False  # 测试环境未保存过 → 回退 .env


def test_put_llm_settings_and_readback(client, auth_headers):
    resp = client.put(
        "/api/settings/llm",
        headers=auth_headers,
        json={
            "provider": "openai_compatible",
            "model": "qwen-flash",
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "sk-test123456",
            "temperature": 0.2,
            "max_tokens": 2048,
            "fallback_model": "qwen-turbo",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["model"] == "qwen-flash"
    assert body["api_key_masked"] == "sk-****3456"
    assert "api_key" not in body
    assert body["configured"] is True
    assert body["fallback_model"] == "qwen-turbo"  # 备用模型已保存

    # 重新读取仍是新值
    got = client.get("/api/settings/llm").json()
    assert got["model"] == "qwen-flash"

    # 热生效：get_llm_config 返回 DB 值
    cfg = get_llm_config()
    assert cfg["model"] == "qwen-flash"
    assert cfg["api_key"] == "sk-test123456"
    assert cfg["fallback_model"] == "qwen-turbo"


def test_put_llm_settings_blank_key_keeps_old(client, auth_headers):
    client.put("/api/settings/llm", headers=auth_headers, json={"model": "qwen-flash", "base_url": "https://x/v1", "api_key": "sk-keepme999"})
    resp = client.put("/api/settings/llm", headers=auth_headers, json={"model": "qwen-max", "base_url": "https://x/v1", "api_key": ""})
    assert resp.status_code == 200
    assert resp.json()["model"] == "qwen-max"
    assert get_llm_config()["api_key"] == "sk-keepme999"  # 空 key 保留旧值


def test_put_llm_settings_validation(client, auth_headers):
    # model 空 → 400
    assert client.put("/api/settings/llm", headers=auth_headers, json={"model": "", "base_url": "https://x/v1"}).status_code == 400
    # base_url 空 → 400
    assert client.put("/api/settings/llm", headers=auth_headers, json={"model": "qwen-flash", "base_url": ""}).status_code == 400
    # 未登录 → 401
    assert client.put("/api/settings/llm", json={"model": "qwen-flash", "base_url": "https://x/v1"}).status_code == 401


def test_llm_test_endpoint_validation(client, auth_headers):
    # 未配置 key → 400 提示
    client.put("/api/settings/llm", headers=auth_headers, json={"model": "qwen-flash", "base_url": "https://x/v1", "api_key": ""})
    cfg = get_llm_config()
    if not cfg.get("api_key"):
        resp = client.post("/api/settings/llm/test")
        assert resp.status_code == 400
        assert "API Key" in resp.json()["detail"]


def test_auth_flow(client):
    # 错误密码 → 401
    assert client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
    # 正确登录 → token
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    token = resp.json()["token"]
    # me 接口
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"
    # 无 token → 401
    assert client.get("/api/auth/me").status_code == 401
