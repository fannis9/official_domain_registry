import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import check_rate, require_admin
from app.models import AuditLog, Domain, User
from app.schemas import AdminDomainOut, AdminQueueOut, AuditLogOut, DomainOut
from app.security import hash_ip, hash_password, utcnow, verify_password
from app.services import verification as vemail

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

CATEGORIES = [
    "software", "nonprofit", "technology", "infrastructure", "finance",
    "government", "education", "media", "ecommerce", "gaming", "ai",
    "cloud", "security", "other",
]


async def _get_row(db: AsyncSession, domain_id: int) -> Domain:
    row = await db.get(Domain, domain_id)
    if not row:
        raise HTTPException(404, "域名不存在")
    return row


def _audit(db: AsyncSession, row: Domain, action: str, detail: str | None = None):
    db.add(AuditLog(domain_id=row.id, action=action, actor="admin", detail=detail))


def _apply_level(row: Domain):
    if row.status == "verified":
        row.verification_level = 4 if (row.registry_type == "official" and row.official_verified) else 3


@router.post("/login")
async def login(payload: dict, request: __import__("fastapi").Request, db: AsyncSession = Depends(get_db)):
    from app.security import create_access_token, create_refresh_token

    ip = request.client.host if request.client else "unknown"
    if await check_rate(db, hash_ip(ip), "admin_login", 5):
        raise HTTPException(401, "登录尝试过于频繁，请 1 分钟后再试")
    username = str(payload.get("username", ""))
    password = str(payload.get("password", ""))
    if secrets.compare_digest(username, settings.admin_username) and secrets.compare_digest(password, settings.admin_password):
        user = await db.scalar(select(User).where(User.username == settings.admin_username))
        if not user:
            user = User(
                username=settings.admin_username,
                email=None,
                password_hash=hash_password(settings.admin_password),
                is_admin=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        access, _ = create_access_token(str(user.id), {"username": user.username, "is_admin": True})
        refresh, _ = create_refresh_token(str(user.id))
        return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}
    raise HTTPException(401, "账号或密码错误")


@router.get("/stats")
async def stats(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    async def count(cond):
        return (await db.scalar(select(func.count()).select_from(Domain).where(cond))) or 0

    return {
        "pending": await count(Domain.status == "pending"),
        "verified": await count(Domain.status == "verified"),
        "rejected": await count(Domain.status == "rejected"),
        "revoked": await count(Domain.status == "revoked"),
        "official": await count(Domain.registry_type == "official"),
        "free": await count(Domain.registry_type == "free"),
    }


@router.get("/domains", response_model=AdminQueueOut)
async def queue(
    q: str = "",
    status: str = "",
    type: str = "",
    sort: str = "newest",
    page: int = Query(default=1, ge=1),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    page_size = 50
    q = q.strip().lower()
    conds = []
    if q:
        pattern = f"%{q}%"
        conds.append(or_(Domain.domain.ilike(pattern), Domain.organization.ilike(pattern)))
    if status in ("pending", "verified", "rejected", "revoked"):
        conds.append(Domain.status == status)
    if type in ("official", "free"):
        conds.append(Domain.registry_type == type)

    total = (await db.scalar(select(func.count()).select_from(Domain).where(*conds))) or 0
    total_pages = max((total + page_size - 1) // page_size, 1)
    page = min(page, total_pages)

    order = {
        "newest": Domain.created_at.desc(),
        "oldest": Domain.created_at.asc(),
        "domain": Domain.domain.asc(),
        "reviewed": Domain.last_reviewed_at.desc(),
    }.get(sort, Domain.created_at.desc())
    rows = (await db.scalars(
        select(Domain).where(*conds).order_by(order).offset((page - 1) * page_size).limit(page_size)
    )).all()

    submitter_ids = {d.submitter_id for d in rows if d.submitter_id}
    submitter_map = {}
    if submitter_ids:
        submitter_map = {
            u.id: u.username for u in (await db.scalars(select(User).where(User.id.in_(submitter_ids)))).all()
        }

    items = []
    for d in rows:
        logs = (await db.scalars(
            select(AuditLog).where(AuditLog.domain_id == d.id).order_by(AuditLog.created_at.desc()).limit(3)
        )).all()
        items.append(
            AdminDomainOut(
                id=d.id,
                domain=d.domain,
                organization=d.organization,
                category=d.category,
                status=d.status,
                verification_level=d.verification_level,
                registry_type=d.registry_type,
                requested_type=d.requested_type,
                ownership_verified=d.ownership_verified,
                official_verified=d.official_verified,
                notes=d.notes,
                submitter_username=submitter_map.get(d.submitter_id),
                submitter_email=d.submitter_email,
                created_at=d.created_at,
                audit_logs=[
                    AuditLogOut(action=log.action, actor=log.actor, detail=log.detail, created_at=log.created_at)
                    for log in logs
                ],
            )
        )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.get("/domains/{domain_id}", response_model=DomainOut)
async def detail(domain_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    return await _get_row(db, domain_id)


@router.post("/domains/{domain_id}/verify", response_model=DomainOut)
async def verify(domain_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await _get_row(db, domain_id)
    if row.status != "pending":
        raise HTTPException(409, f"当前状态 {row.status} 不能直接通过")
    row.status = "verified"
    row.verified_at = utcnow()
    row.last_reviewed_at = utcnow()
    _apply_level(row)
    _audit(db, row, "verified", "人工审核通过")
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/reject", response_model=DomainOut)
async def reject(
    domain_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_row(db, domain_id)
    if row.status != "pending":
        raise HTTPException(409, f"当前状态 {row.status} 不能驳回")
    row.status = "rejected"
    row.last_reviewed_at = utcnow()
    _audit(db, row, "rejected", str(payload.get("reason", "") or "驳回")[:2000] or None)
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/revoke", response_model=DomainOut)
async def revoke(
    domain_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_row(db, domain_id)
    if row.status != "verified":
        raise HTTPException(409, "只有已验证域名可以撤销")
    row.status = "revoked"
    row.verification_level = 0
    row.last_reviewed_at = utcnow()
    _audit(db, row, "revoked", str(payload.get("reason", "") or "撤销")[:2000] or None)
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/restore", response_model=DomainOut)
async def restore(domain_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await _get_row(db, domain_id)
    if row.status != "revoked":
        raise HTTPException(409, "只有已撤销域名可以恢复")
    row.status = "verified"
    row.verified_at = utcnow()
    row.last_reviewed_at = utcnow()
    _apply_level(row)
    _audit(db, row, "restored", "撤销后恢复验证")
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/reopen", response_model=DomainOut)
async def reopen(domain_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await _get_row(db, domain_id)
    if row.status != "rejected":
        raise HTTPException(409, "只有已驳回域名可以重新打开")
    row.status = "pending"
    row.last_reviewed_at = utcnow()
    _audit(db, row, "reopened", "重新打开进入待审核")
    await db.commit()
    await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/set-type", response_model=DomainOut)
async def set_type(
    domain_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_row(db, domain_id)
    registry_type = str(payload.get("registry_type", ""))
    if registry_type not in ("official", "free"):
        raise HTTPException(400, "类型必须是 official 或 free")
    if row.registry_type != registry_type:
        old = row.registry_type
        row.registry_type = registry_type
        if registry_type == "free":
            row.official_verified = False
        row.last_reviewed_at = utcnow()
        _apply_level(row)
        _audit(db, row, "type_changed", f"{old} -> {registry_type}")
        await db.commit()
        await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/confirm-official", response_model=DomainOut)
async def confirm_official(domain_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await _get_row(db, domain_id)
    if row.status != "verified":
        raise HTTPException(409, "只有已验证域名可以确认官方身份")
    if row.registry_type != "official":
        raise HTTPException(409, "请先将该域名设为官方域名")
    if not row.official_verified:
        row.official_verified = True
        row.verification_level = 4
        row.last_reviewed_at = utcnow()
        _audit(db, row, "official_confirmed", "确认官方身份（品牌/组织代表）")
        await db.commit()
        await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/set-category", response_model=DomainOut)
async def set_category(
    domain_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_row(db, domain_id)
    category = str(payload.get("category", "")).strip().lower()[:80] or None
    if category and category not in CATEGORIES:
        raise HTTPException(400, "未知类别")
    if row.category != category:
        old = row.category
        row.category = category
        row.last_reviewed_at = utcnow()
        _audit(db, row, "category_changed", f"{old or '未分类'} -> {category or '未分类'}")
        await db.commit()
        await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/set-org", response_model=DomainOut)
async def set_org(
    domain_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    row = await _get_row(db, domain_id)
    org = str(payload.get("organization", "")).strip()[:200]
    if not org:
        raise HTTPException(400, "组织名不能为空")
    if row.organization != org:
        old = row.organization
        row.organization = org
        row.last_reviewed_at = utcnow()
        _audit(db, row, "org_changed", f"{old} -> {org}")
        await db.commit()
        await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/remove-from-org", response_model=DomainOut)
async def remove_from_org(domain_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await _get_row(db, domain_id)
    if row.organization != row.domain:
        old = row.organization
        row.organization = row.domain
        row.last_reviewed_at = utcnow()
        _audit(db, row, "org_removed", f"{old} -> 独立域名")
        await db.commit()
        await db.refresh(row)
    return row


@router.post("/domains/{domain_id}/delete")
async def delete(domain_id: int, _: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    row = await _get_row(db, domain_id)
    if row.status == "pending":
        raise HTTPException(409, "待审核域名不能直接删除，请先驳回")
    await db.delete(row)
    await db.commit()
    return {"deleted": True}


@router.post("/batch")
async def batch(
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    ids = [int(x) for x in str(payload.get("ids", "")).split(",") if x.strip().isdigit()]
    action = str(payload.get("action", ""))
    reason = str(payload.get("reason", "") or "批量操作")[:2000]
    if action not in ("verify", "reject", "official", "free"):
        raise HTTPException(400, "未知批量操作")
    if not ids or len(ids) > 200:
        raise HTTPException(400, "请选择要操作的域名")
    rows = (await db.scalars(select(Domain).where(Domain.id.in_(ids)))).all()
    for row in rows:
        if action == "verify" and row.status == "pending":
            row.status = "verified"
            row.verified_at = utcnow()
            row.last_reviewed_at = utcnow()
            _apply_level(row)
            _audit(db, row, "verified", "批量审核通过")
        elif action == "reject" and row.status == "pending":
            row.status = "rejected"
            row.last_reviewed_at = utcnow()
            _audit(db, row, "rejected", reason)
        elif action == "official" and row.registry_type != "official":
            row.registry_type = "official"
            row.last_reviewed_at = utcnow()
            _apply_level(row)
            _audit(db, row, "type_changed", "free -> official (批量)")
        elif action == "free" and row.registry_type != "free":
            row.registry_type = "free"
            row.official_verified = False
            row.last_reviewed_at = utcnow()
            _apply_level(row)
            _audit(db, row, "type_changed", "official -> free (批量)")
    await db.commit()
    return {"updated": len(rows)}


@router.get("/orgs")
async def orgs(_: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Domain).order_by(Domain.organization.asc(), Domain.domain.asc()))).all()
    groups: dict[str, list] = {}
    for d in rows:
        groups.setdefault(d.organization, []).append(
            {"id": d.id, "domain": d.domain, "status": d.status, "registry_type": d.registry_type}
        )
    result = []
    for org_name, members in groups.items():
        # 组织名=唯一成员域名 的是独立域名,不算组织,不在组织管理页显示
        if len(members) == 1 and members[0]["domain"] == org_name:
            continue
        result.append({"organization": org_name, "members": members})
    result.sort(key=lambda kv: kv["organization"].lower())
    return result


@router.post("/orgs/rename")
async def org_rename(
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    old = str(payload.get("old", "")).strip()
    new = str(payload.get("new", "")).strip()[:200]
    if not old or not new:
        raise HTTPException(400, "组织名不能为空")
    rows = (await db.scalars(select(Domain).where(Domain.organization == old))).all()
    for row in rows:
        if row.organization != new:
            prev = row.organization
            row.organization = new
            row.last_reviewed_at = utcnow()
            _audit(db, row, "org_changed", f"{prev} -> {new}")
    await db.commit()
    return {"renamed": len(rows)}


@router.post("/orgs/dissolve")
async def org_dissolve(
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    org = str(payload.get("organization", "")).strip()
    rows = (await db.scalars(select(Domain).where(Domain.organization == org))).all()
    for row in rows:
        if row.organization != row.domain:
            prev = row.organization
            row.organization = row.domain
            row.last_reviewed_at = utcnow()
            _audit(db, row, "org_removed", f"{prev} -> 独立域名")
    await db.commit()
    return {"dissolved": len(rows)}


@router.get("/users")
async def users(
    q: str = "",
    page: int = Query(default=1, ge=1),
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    page_size = 50
    stmt = select(User)
    if q.strip():
        pattern = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(User.username.ilike(pattern), User.email.ilike(pattern)))
    rows = (await db.scalars(stmt.order_by(User.created_at.desc()).offset((page - 1) * page_size).limit(page_size))).all()
    ids = [u.id for u in rows]
    counts = {}
    if ids:
        result = await db.execute(
            select(Domain.submitter_id, func.count()).where(Domain.submitter_id.in_(ids)).group_by(Domain.submitter_id)
        )
        counts = dict(result.all())
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "is_admin": u.is_admin,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "submissions": counts.get(u.id, 0),
        }
        for u in rows
    ]


@router.post("/users/{user_id}/remove")
async def remove_user(
    user_id: int,
    payload: dict,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    reason = str(payload.get("reason", "")).strip()
    if not reason:
        raise HTTPException(400, "请填写移除理由")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(404, "用户不存在")
    email, username = user.email, user.username
    await db.execute(update(Domain).where(Domain.submitter_id == user.id).values(submitter_id=None))
    await db.delete(user)
    await db.commit()
    if email:
        from starlette.concurrency import run_in_threadpool

        try:
            await run_in_threadpool(
                vemail.send_email,
                email,
                "你的账号已被移除 - Official Domain Registry",
                f"你的账号 {username} 已被管理员移除。\n\n移除理由：{reason}\n\n如有疑问，请联系管理员。\n\nOfficial Domain Registry",
            )
        except Exception:
            pass
    return {"removed": True}
