"""v1 SQLite -> v2 PostgreSQL 数据迁移(一次性脚本)。

用法(在 v2 容器内执行):
    python scripts/migrate_v1.py /path/to/v1/registry.db
"""
import asyncio
import sqlite3
import sys
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.config import settings
from app.models import AuditLog, Domain, User


def _aware(dt_str: str) -> datetime | None:
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except ValueError:
        dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M:%S.%f")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


async def migrate(v1_path: str):
    conn = sqlite3.connect(v1_path)
    conn.row_factory = sqlite3.Row

    engine = create_async_engine(settings.database_url)
    from app.models import Base

    async with engine.begin() as txn:
        await txn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        # users
        users = conn.execute("SELECT id, username, email, password_hash, created_at FROM users").fetchall()
        id_map = {}
        for u in users:
            row = await session.execute(select(User).where(User.username == u["username"]))
            if row.scalar_one_or_none():
                continue
            new_user = User(
                username=u["username"],
                email=u["email"],
                password_hash=u["password_hash"],
                is_admin=False,
                created_at=_aware(u["created_at"]),
            )
            session.add(new_user)
            await session.flush()
            id_map[u["id"]] = new_user.id

        # domains
        domains = conn.execute("SELECT * FROM domains").fetchall()
        domain_id_map = {}
        for d in domains:
            new_domain = Domain(
                domain=d["domain"],
                organization=d["organization"],
                category=d["category"],
                status=d["status"],
                registry_type=d["registry_type"] if "registry_type" in d.keys() else "free",
                verification_level=d["verification_level"] or 0,
                verification_token=d["verification_token"],
                verification_expires_at=_aware(d["verification_expires_at"]) if d["verification_expires_at"] else None,
                ownership_method=d["ownership_method"],
                submitter_email=d["submitter_email"],
                submitter_id=id_map.get(d["submitter_id"]) if d["submitter_id"] else None,
                ownership_verified=bool(d["ownership_verified"]) if "ownership_verified" in d.keys() else False,
                official_verified=bool(d["official_verified"]) if "official_verified" in d.keys() else False,
                requested_type=d["requested_type"] if "requested_type" in d.keys() else "free",
                notes=d["notes"],
                created_at=_aware(d["created_at"]),
                updated_at=_aware(d["updated_at"]),
                verified_at=_aware(d["verified_at"]) if d["verified_at"] else None,
                last_reviewed_at=_aware(d["last_reviewed_at"]) if d["last_reviewed_at"] else None,
            )
            session.add(new_domain)
            await session.flush()
            domain_id_map[d["id"]] = new_domain.id

        # audit logs
        logs = conn.execute("SELECT * FROM audit_logs").fetchall()
        for log in logs:
            if log["domain_id"] not in domain_id_map:
                continue
            session.add(
                AuditLog(
                    domain_id=domain_id_map[log["domain_id"]],
                    action=log["action"],
                    actor=log["actor"],
                    detail=log["detail"],
                    created_at=_aware(log["created_at"]),
                )
            )

        await session.commit()

    conn.close()
    await engine.dispose()
    print(f"migrated users={len(users)} domains={len(domains)} logs={len(logs)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    asyncio.run(migrate(sys.argv[1]))
