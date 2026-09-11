from fastapi import FastAPI, Depends, HTTPException
import jwt

from app.config import assert_safe_settings, settings
from app.db import get_db
from app.routers import admin
from app.schemas import TokenOut

assert_safe_settings()

admin_app = FastAPI(title=f"{settings.app_name} Admin API", version="2.0.0")


@admin_app.get("/api/v1/healthz")
async def healthz():
    return {"status": "ok"}


@admin_app.post("/api/v1/auth/refresh", response_model=TokenOut)
async def admin_refresh(payload: dict, db=Depends(get_db)):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models import User
    from app.security import create_access_token, create_refresh_token, decode_token

    refresh_token = str(payload.get("refresh_token", ""))
    try:
        data = decode_token(refresh_token, "refresh")
        user_id = int(data["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(401, "刷新凭证无效或已过期，请重新登录")
    user = await db.get(User, user_id)
    if not user or not user.is_admin:
        raise HTTPException(401, "用户不存在或非管理员")
    access, _ = create_access_token(str(user.id), {"username": user.username, "is_admin": True})
    refresh, _ = create_refresh_token(str(user.id))
    return TokenOut(access_token=access, refresh_token=refresh, expires_in=30 * 60)


admin_app.include_router(admin.router)
