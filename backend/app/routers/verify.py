import base64
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.db import get_db
from app.deps import check_rate
from app.schemas import OwnershipVerify
from app.security import hash_ip
from app.services import verification as vcode

router = APIRouter(prefix="/api/v1", tags=["verification"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("/captcha")
async def captcha(request: Request, db: AsyncSession = Depends(get_db)):
    if await check_rate(db, hash_ip(_ip(request)), "captcha", 30):
        raise HTTPException(429, "验证码获取过于频繁，请稍后再试")
    token, png = await run_in_threadpool(vcode.issue_captcha)
    return {
        "captcha_token": token,
        "image": "data:image/png;base64," + base64.b64encode(png).decode(),
    }


@router.post("/email-code")
async def email_code(
    request: Request,
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    email = str(payload.get("email", "")).strip().lower()
    captcha_token = str(payload.get("captcha_token", ""))
    captcha_answer = str(payload.get("captcha_answer", ""))
    if not EMAIL_RE.match(email):
        raise HTTPException(400, "请填写有效邮箱")
    if await check_rate(db, hash_ip(_ip(request)), "email_code", 5):
        raise HTTPException(429, "发送过于频繁，请稍后再试")
    if not await run_in_threadpool(vcode.verify_captcha, captcha_token, captcha_answer):
        raise HTTPException(400, "图形验证码错误或已过期，请刷新后重试")

    code = vcode.new_email_code()
    try:
        await run_in_threadpool(vcode.send_verification_email, email, code)
    except RuntimeError:
        raise HTTPException(502, "邮件服务未配置，请联系管理员")
    except Exception:
        raise HTTPException(502, "邮件发送失败，请稍后再试")

    email_token = await run_in_threadpool(vcode.issue_email_code, email, code)
    return {"email_token": email_token, "message": "验证码已发送，10 分钟内有效"}


@router.post("/ownership/verify")
async def ownership_verify(
    payload: OwnershipVerify,
    request: Request,
    user=Depends(__import__("app.deps", fromlist=["get_current_user"]).get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select

    from app.models import AuditLog, Domain

    domain = payload.domain.strip().lower().rstrip(".")
    row = await db.scalar(select(Domain).where(Domain.domain == domain, Domain.submitter_id == user.id))
    if not row:
        raise HTTPException(404, "未找到你提交的该域名")
    if row.verification_expires_at:
        expires = row.verification_expires_at
        if expires.tzinfo is None:
            from datetime import timezone as _tz

            expires = expires.replace(tzinfo=_tz.utc)
        if expires < vcode.utcnow():
            raise HTTPException(410, "验证 Token 已过期，请重新提交域名获取新 Token")
    if row.ownership_verified:
        return {"verified": True, "domain": row.domain, "verification_level": row.verification_level}

    from app.services.reputation import check_dns_txt, check_well_known

    if row.ownership_method == "well_known":
        ok = await run_in_threadpool(check_well_known, row.domain, row.verification_token or "")
    else:
        ok = await run_in_threadpool(check_dns_txt, row.domain, row.verification_token or "")
    if not ok:
        raise HTTPException(400, "未找到验证记录，请检查 TXT 记录或 well-known 文件")

    row.ownership_verified = True
    row.verification_level = max(row.verification_level, 1)
    row.last_reviewed_at = vcode.utcnow()
    db.add(AuditLog(domain_id=row.id, action="ownership_verified", actor=user.username, detail=row.ownership_method))
    await db.commit()
    return {"verified": True, "domain": row.domain, "verification_level": row.verification_level}
