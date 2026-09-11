import secrets
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models import ApiKey, User
from app.security import decode_token, hash_api_key

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "请先登录")
    return await _authenticate(credentials.credentials, db)


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None
    try:
        return await _authenticate(credentials.credentials, db)
    except HTTPException:
        return None


async def _authenticate(token: str, db: AsyncSession) -> User:
    if token.startswith(f"{settings.api_key_prefix}."):
        return await _auth_api_key(token, db)
    return await _auth_jwt(token, db)


async def _auth_jwt(token: str, db: AsyncSession) -> User:
    try:
        payload = decode_token(token, "access")
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "凭证无效或已过期，请重新登录")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


async def _auth_api_key(token: str, db: AsyncSession) -> User:
    raw = token[len(settings.api_key_prefix) + 1:]
    key_hash = hash_api_key(raw)
    key = await db.scalar(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.revoked.is_(False))
    )
    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "API Key 无效")
    user = await db.get(User, key.user_id)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在")
    return user


async def require_admin(
    request: Request,
    user: User = Depends(get_current_user),
) -> User:
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return user


async def csrf_check(request: Request):
    header = request.headers.get("x-csrf-token", "")
    expected = request.session.get("csrf_token") if hasattr(request, "session") else None
    if not expected or not header or not secrets.compare_digest(expected, header):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF 校验失败")


def rate_limit_hit(count: int, limit: int) -> bool:
    return count >= limit


async def check_rate(db: AsyncSession, ip_hash: str, action: str, limit: int) -> bool:
    from sqlalchemy import func, delete

    from app.models import RateAttempt

    cutoff = __import__("app.security", fromlist=["utcnow"]).utcnow() - timedelta(minutes=1)
    count = (
        await db.scalar(
            select(func.count())
            .select_from(RateAttempt)
            .where(RateAttempt.ip_hash == ip_hash, RateAttempt.action == action, RateAttempt.created_at >= cutoff)
        )
        or 0
    )
    if count >= limit:
        return True
    await db.execute(delete(RateAttempt).where(RateAttempt.created_at < cutoff - timedelta(hours=1)))
    db.add(RateAttempt(ip_hash=ip_hash, action=action))
    return False
