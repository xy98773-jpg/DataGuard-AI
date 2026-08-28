"""设置 API：LLM 模型配置（UI 可视化 + 热生效 + 连接测试）。"""

import time

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from app.api.auth import get_current_user
from app.services.llm_settings import get_llm_config, public_config, save_llm_config

router = APIRouter(tags=["settings"])


class LLMConfigIn(BaseModel):
    provider: str = "openai_compatible"
    model: str = ""
    api_key: str = ""  # 空 = 保留旧值
    base_url: str = ""
    temperature: float = 0.0
    max_tokens: int = 4096
    fallback_model: str = ""  # 备用模型（主模型失败自动切换）
    fallback_base_url: str = ""
    fallback_api_key: str = ""  # 空 = 保留旧值


@router.get("/settings/llm")
def get_llm_settings() -> dict:
    """返回当前 LLM 配置（api_key 脱敏，仅末 4 位）。"""
    return public_config()


@router.put("/settings/llm")
def put_llm_settings(cfg: LLMConfigIn, user: dict = Depends(get_current_user)) -> dict:
    """保存 LLM 配置并热生效（需登录；下次治理立即使用新模型）。"""
    try:
        saved = save_llm_config(cfg.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return public_config()


@router.post("/settings/llm/test")
def test_llm_connection() -> dict:
    """用当前配置发一次最小请求验证连通性。"""
    cfg = get_llm_config()
    if not cfg.get("api_key"):
        raise HTTPException(status_code=400, detail="尚未配置 API Key，请先在设置页保存")
    try:
        llm = ChatOpenAI(
            model=cfg["model"],
            base_url=cfg["base_url"] or None,
            api_key=cfg["api_key"] or "not-needed",
            temperature=cfg.get("temperature", 0.0),
            max_tokens=cfg.get("max_tokens", 4096),
            max_retries=0,
            timeout=30,
        )
        start = time.time()
        resp = llm.invoke([HumanMessage(content="请只回复：连接成功")])
        elapsed = round(time.time() - start, 2)
        reply = (resp.content or "")[:80]
        return {
            "ok": True,
            "elapsed": elapsed,
            "model": cfg["model"],
            "reply": reply,
        }
    except Exception as e:  # noqa: BLE001 - 把真实错误回显给用户排查
        raise HTTPException(status_code=400, detail=f"连接失败：{e}")
