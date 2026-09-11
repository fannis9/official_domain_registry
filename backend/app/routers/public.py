from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import settings
from app.db import get_db
from app.deps import check_rate, get_current_user
from app.models import AuditLog, Domain, User
from app.schemas import DomainOut, DomainSubmit, DomainSubmitOut, EmailUpdate
from app.security import hash_ip, utcnow
from app.services.reputation import domain_checks_cached

router = APIRouter(prefix="/api/v1", tags=["public"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}


@router.get("/status/{domain}")
async def domain_status(domain: str, db: AsyncSession = Depends(get_db)):
    domain = domain.strip().lower().rstrip(".")
    row = await db.scalar(select(Domain).where(Domain.domain == domain))
    if not row:
        return {"domain": domain, "in_registry": False, "status": "unknown"}
    return {
        "domain": row.domain,
        "in_registry": True,
        "status": row.status,
        "registry_type": row.registry_type,
        "requested_type": row.requested_type,
        "verification_level": row.verification_level,
        "ownership_verified": row.ownership_verified,
        "official_verified": row.official_verified,
        "organization": row.organization,
        "category": row.category,
    }


@router.get("/domain/{domain}", response_model=DomainOut)
async def lookup(domain: str, db: AsyncSession = Depends(get_db)):
    domain = domain.lower().rstrip(".")
    row = await db.scalar(select(Domain).where(Domain.domain == domain))
    if not row or row.status != "verified":
        raise HTTPException(404, "未找到已验证的官方域名")
    return row


@router.get("/domains", response_model=list[DomainOut])
async def list_verified(
    limit: int = Query(default=50, ge=1, le=200),
    type: str = "all",
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Domain).where(Domain.status == "verified")
    if type in ("official", "free"):
        stmt = stmt.where(Domain.registry_type == type)
    rows = await db.scalars(stmt.order_by(Domain.domain.asc()).limit(limit))
    return list(rows)


@router.get("/check")
async def check_domain(domain: str, db: AsyncSession = Depends(get_db)):
    domain = domain.strip().lower().rstrip(".")
    row = await db.scalar(select(Domain).where(Domain.domain == domain))
    if not row:
        return {"exists": False, "domain": domain}
    return {"exists": True, "domain": domain, "status": row.status}


@router.get("/search")
async def search(
    q: str = "",
    page: int = Query(default=1, ge=1),
    type: str = "all",
    db: AsyncSession = Depends(get_db),
):
    page_size = 25
    q = q.strip().lower()
    stmt = select(Domain).where(Domain.status == "verified")
    if type in ("official", "free"):
        stmt = stmt.where(Domain.registry_type == type)
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(or_(Domain.domain.ilike(pattern), Domain.organization.ilike(pattern)))
    rows = await db.scalars(
        stmt.order_by(Domain.domain.asc()).offset((page - 1) * page_size).limit(page_size)
    )
    return list(rows)


@router.post("/submissions", response_model=DomainSubmitOut, status_code=201)
async def submit(
    payload: DomainSubmit,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ip_hash = hash_ip(request.client.host if request.client else "unknown")
    if await check_rate(db, ip_hash, "submission", settings.rate_limit_per_minute):
        raise HTTPException(429, "提交过于频繁，请稍后再试")

    existing = await db.scalar(select(Domain).where(Domain.domain == payload.domain))
    if existing:
        raise HTTPException(409, "该域名已经存在")

    checks = await run_in_threadpool(domain_checks_cached, payload.domain)
    if not checks["dns_resolves"]:
        raise HTTPException(400, "域名无法解析，请确认域名正确")

    row = Domain(
        domain=payload.domain,
        organization=payload.organization,
        category=payload.category,
        status="pending",
        verification_level=0,
        verification_token=__import__("secrets").token_urlsafe(32),
        verification_expires_at=utcnow() + __import__("datetime").timedelta(minutes=settings.verification_ttl_minutes),
        ownership_method=payload.ownership_method,
        registry_type="free",
        requested_type=payload.registry_type,
        submitter_email=payload.submitter_email or user.email,
        submitter_id=user.id,
        notes=payload.notes,
    )
    db.add(row)
    await db.flush()
    checks_summary = (
        f"dns={'ok' if checks['dns_resolves'] else 'fail'}, "
        f"https={'ok' if checks['https_reachable'] else 'fail'}, "
        f"tls={'ok' if checks['tls_ok'] else 'fail'}"
    )
    db.add(AuditLog(domain_id=row.id, action="submitted", actor=user.username, detail=checks_summary))
    await db.commit()
    await db.refresh(row)
    result = DomainSubmitOut.model_validate(row)
    result.verification_token = row.verification_token or ""
    return result


@router.get("/me/domains", response_model=list[DomainOut])
async def my_domains(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = await db.scalars(
        select(Domain).where(Domain.submitter_id == user.id).order_by(Domain.created_at.desc())
    )
    return list(rows)


@router.post("/me/email")
async def update_email(
    payload: EmailUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.services.verification import verify_email_code

    email = payload.email.strip().lower()
    if not verify_email_code(payload.email_token, email, payload.code):
        raise HTTPException(400, "邮箱验证码无效或已过期，请重新发送")
    from sqlalchemy import select as _select

    if await db.scalar(_select(User).where(User.email == email, User.id != user.id)):
        raise HTTPException(409, "该邮箱已被其他账号使用")
    user.email = email
    await db.commit()
    return {"email": email}


@router.get("/me/api-keys")
async def list_api_keys(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import ApiKey

    rows = await db.scalars(select(ApiKey).where(ApiKey.user_id == user.id).order_by(ApiKey.created_at.desc()))
    return [
        {
            "id": k.id,
            "name": k.name,
            "created_at": k.created_at.isoformat() if k.created_at else None,
            "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
            "revoked": k.revoked,
        }
        for k in rows
    ]


@router.post("/me/api-keys", status_code=201)
async def create_api_key(
    payload: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import ApiKey
    from app.security import new_api_key

    name = str(payload.get("name", "")).strip()[:100]
    if not name:
        raise HTTPException(400, "请填写 Key 名称")
    count = await db.scalar(
        select(func.count()).select_from(ApiKey).where(ApiKey.user_id == user.id, ApiKey.revoked.is_(False))
    ) or 0
    if count >= 10:
        raise HTTPException(400, "每个账号最多 10 个有效 API Key")
    raw, key_hash = new_api_key()
    key = ApiKey(user_id=user.id, name=name, key_hash=key_hash)
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return {
        "id": key.id,
        "name": key.name,
        "revoked": False,
        "created_at": key.created_at.isoformat() if key.created_at else None,
        "key": f"{settings.api_key_prefix}.{raw}",
    }


@router.post("/me/api-keys/{key_id}/revoke")
async def revoke_api_key(key_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    from app.models import ApiKey

    key = await db.get(ApiKey, key_id)
    if not key or key.user_id != user.id:
        raise HTTPException(404, "API Key 不存在")
    key.revoked = True
    await db.commit()
    return {"revoked": True}
