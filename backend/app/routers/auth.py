import re

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.deps import check_rate, get_current_user
from app.models import User
from app.schemas import LoginIn, RegisterIn, TokenOut
from app.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_ip,
    hash_password,
    verify_password,
)
from app.services.verification import verify_email_code

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/register", status_code=201)
async def register(payload: RegisterIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip_hash = hash_ip(_ip(request))
    if await check_rate(db, ip_hash, "register", 10):
        raise HTTPException(429, "注册过于频繁，请稍后再试")

    username = payload.username.strip()
    email = payload.email.strip().lower()
    if not USERNAME_RE.match(username):
        raise HTTPException(400, "用户名需为 3-32 位字母、数字、下划线、点或短横线")
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "请填写有效邮箱")
    if await db.scalar(select(User).where(User.username == username)):
        raise HTTPException(400, "用户名已被占用")
    if await db.scalar(select(User).where(User.email == email)):
        raise HTTPException(400, "该邮箱已被注册")

    if not verify_email_code(payload.email_token, email, payload.code):
        raise HTTPException(400, "邮箱验证码无效或已过期，请重新发送")

    user = User(username=username, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return await _token_pair(user)


@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    ip_hash = hash_ip(_ip(request))
    if await check_rate(db, ip_hash, "login", 10):
        raise HTTPException(429, "登录尝试过于频繁，请稍后再试")

    user = await db.scalar(select(User).where(User.username == payload.username.strip()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    return await _token_pair(user)


@router.post("/refresh", response_model=TokenOut)
async def refresh(payload: dict, db: AsyncSession = Depends(get_db)):
    refresh_token = payload.get("refresh_token", "")
    try:
        data = decode_token(refresh_token, "refresh")
        user_id = int(data["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "刷新凭证无效或已过期，请重新登录")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(401, "用户不存在")
    return await _token_pair(user)


@router.get("/whoami")
async def whoami(user: User = Depends(get_current_user)):
    return {"logged_in": True, "username": user.username, "is_admin": user.is_admin}


async def _token_pair(user: User) -> TokenOut:
    access, _ = create_access_token(str(user.id), {"username": user.username, "is_admin": user.is_admin})
    refresh, _ = create_refresh_token(str(user.id))
    return TokenOut(access_token=access, refresh_token=refresh, expires_in=30 * 60)
