"""认证服务：管理员账号初始化、密码哈希（pbkdf2 标准库）、JWT 签发与校验。

- 默认管理员：admin / admin123（首次登录后可在 README 提示下修改；当前单管理员）
- 密码用 hashlib.pbkdf2_hmac（标准库，无需 bcrypt 编译依赖）
- JWT 用 pyjwt，密钥来自 settings.auth_secret（.env DG_AUTH_SECRET），默认本地随机
"""

import hashlib
import hmac
import secrets
import time
from datetime import datetime

import jwt
from loguru import logger

from app.config import settings
from app.models import User
from app.storage.database import SessionLocal

TOKEN_TTL_SECONDS = 24 * 3600  # 24h

_DEFAULT_ADMIN = "admin"
_DEFAULT_ADMIN_PASSWORD = "admin123"


def _hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
    return f"pbkdf2${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split("$")
        if algo != "pbkdf2":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100_000).hex()
        return hmac.compare_digest(candidate, digest)
    except (ValueError, AttributeError):
        return False


def ensure_admin() -> None:
    """首次启动创建默认管理员（不存在时）。"""
    with SessionLocal() as session:
        exists = session.query(User).filter(User.username == _DEFAULT_ADMIN).first()
        if exists:
            return
        session.add(
            User(
                username=_DEFAULT_ADMIN,
                password_hash=_hash_password(_DEFAULT_ADMIN_PASSWORD),
                is_admin=1,
            )
        )
        session.commit()
    logger.info("已初始化默认管理员账号: {} / {}", _DEFAULT_ADMIN, _DEFAULT_ADMIN_PASSWORD)


def authenticate(username: str, password: str) -> dict | None:
    """校验用户名密码，成功返回用户 dict。"""
    with SessionLocal() as session:
        user = session.query(User).filter(User.username == username.strip()).first()
        if user is None:
            return None
        if not _verify_password(password, user.password_hash):
            return None
        return {"id": user.id, "username": user.username, "is_admin": bool(user.is_admin)}


def create_token(user: dict) -> str:
    payload = {
        "sub": user["id"],
        "username": user["username"],
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, settings.auth_secret, algorithm="HS256")


def verify_token(token: str) -> dict | None:
    """校验 JWT，返回 payload；无效/过期返回 None。"""
    try:
        payload = jwt.decode(token, settings.auth_secret, algorithms=["HS256"])
        return payload
    except jwt.PyJWTError:
        return None
