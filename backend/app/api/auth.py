"""认证 API：登录 / 当前用户信息。"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from app.services.auth_service import authenticate, create_token, verify_token

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/auth/login")
def login(body: LoginIn) -> dict:
    user = authenticate(body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": create_token(user), "username": user["username"], "is_admin": user["is_admin"]}


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI 依赖：校验 Bearer token，供受保护接口使用。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="未登录或登录已过期")
    payload = verify_token(authorization[7:])
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return {"username": payload.get("username", ""), "is_admin": True}


@router.get("/auth/me")
def me(user: dict = Depends(get_current_user)) -> dict:
    return user
