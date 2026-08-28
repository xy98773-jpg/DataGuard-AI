"""LLM 运行时配置服务：读写 llm_settings 表（未配置时回退 .env 默认）。

设计：
- 页面保存的配置存在业务库 llm_settings（单行 id="default"），写后**立即生效**
- providers 每次构造 client 时经 get_llm_config() 读取 → 新治理即用新模型，无需重启
- api_key 只在此层落库（明文，本地库），接口返回必须经 mask_api_key 脱敏
"""

from datetime import datetime

from loguru import logger

from app.config import settings
from app.models import LLMSetting
from app.storage.database import SessionLocal

_DEFAULT_ID = "default"


def _fallback() -> dict:
    """.env / Settings 默认值（首次未配置时使用）。"""
    return {
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "api_key": settings.llm_api_key,
        "base_url": settings.llm_base_url,
        "temperature": settings.llm_temperature,
        "max_tokens": settings.llm_max_tokens,
    }


def get_llm_config() -> dict:
    """读取当前生效配置（DB 优先，未保存则回退 .env 默认）。"""
    with SessionLocal() as session:
        row = session.query(LLMSetting).filter(LLMSetting.id == _DEFAULT_ID).first()
    if row is None:
        return _fallback()
    return {
        "provider": row.provider or settings.llm_provider,
        "model": row.model or settings.llm_model,
        "api_key": row.api_key or settings.llm_api_key,
        "base_url": row.base_url or settings.llm_base_url,
        "temperature": row.temperature if row.temperature is not None else settings.llm_temperature,
        "max_tokens": row.max_tokens or settings.llm_max_tokens,
    }


def save_llm_config(cfg: dict) -> dict:
    """保存配置（upsert 单行）。api_key 传空字符串 = 保留旧值。

    校验：model / base_url 非空。
    """
    model = (cfg.get("model") or "").strip()
    base_url = (cfg.get("base_url") or "").strip()
    if not model:
        raise ValueError("model 不能为空")
    if not base_url:
        raise ValueError("base_url 不能为空")

    current = get_llm_config()
    api_key = (cfg.get("api_key") or "").strip()
    if not api_key:
        api_key = current.get("api_key", "")

    with SessionLocal() as session:
        row = session.query(LLMSetting).filter(LLMSetting.id == _DEFAULT_ID).first()
        if row is None:
            row = LLMSetting(id=_DEFAULT_ID)
            session.add(row)
        row.provider = (cfg.get("provider") or "openai_compatible").strip()
        row.model = model
        row.api_key = api_key
        row.base_url = base_url
        try:
            row.temperature = float(cfg.get("temperature", 0.0))
        except (TypeError, ValueError):
            row.temperature = 0.0
        try:
            row.max_tokens = int(cfg.get("max_tokens", 4096))
        except (TypeError, ValueError):
            row.max_tokens = 4096
        row.updated_at = datetime.utcnow()
        session.commit()

    logger.info("LLM 配置已保存并热生效: model={} base_url={}", model, base_url)
    return get_llm_config()


def mask_api_key(key: str) -> str:
    """脱敏：只保留末 4 位。sk-abc12345 -> sk-****2345"""
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return key[:3] + "****" + key[-4:]


def public_config() -> dict:
    """接口返回用：api_key 脱敏 + updated_at。"""
    cfg = get_llm_config()
    cfg["api_key_masked"] = mask_api_key(cfg.get("api_key", ""))
    cfg.pop("api_key", None)
    with SessionLocal() as session:
        row = session.query(LLMSetting).filter(LLMSetting.id == _DEFAULT_ID).first()
    cfg["configured"] = row is not None
    cfg["updated_at"] = row.updated_at.strftime("%Y-%m-%d %H:%M") if row and row.updated_at else ""
    return cfg
