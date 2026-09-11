import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.admin_app import admin_app  # noqa: E402
from app.main import app  # noqa: E402


def _auth_headers(c, username, password="password123"):
    r = c.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _register(c, username, email, monkeypatch, admin=False):
    sent = []
    monkeypatch.setattr(
        "app.services.verification.send_verification_email",
        lambda to, code: sent.append((to, code)),
    )
    monkeypatch.setattr("app.services.verification.issue_captcha", _fake_captcha)
    r = c.post("/api/v1/captcha")
    assert r.status_code == 200, r.text
    data = r.json()
    r = c.post("/api/v1/email-code", json={
        "email": email, "captcha_token": data["captcha_token"], "captcha_answer": "abcd",
    })
    assert r.status_code == 200, r.text
    email_token = r.json()["email_token"]
    assert sent and sent[0][1].isdigit() and len(sent[0][1]) == 6
    code = sent[0][1]
    r = c.post("/api/v1/auth/register", json={
        "username": username, "password": "password123", "email": email,
        "code": code, "email_token": email_token,
    })
    assert r.status_code == 201, r.text
    return r.json()


def _fake_captcha():
    import hashlib
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.config import settings
    from app.services.verification import render_captcha_image

    code = "abcd"
    payload = {
        "code_hash": hashlib.sha256(code.encode()).hexdigest(),
        "type": "captcha",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, render_captcha_image(code)


def test_health_and_metrics():
    with TestClient(app) as c:
        assert c.get("/api/v1/health").json()["status"] == "ok"
        assert "odr_requests_total" in c.get("/metrics").text


def test_register_email_flow(monkeypatch):
    with TestClient(app) as c:
        tokens = _register(c, "v2user", "v2@example.com", monkeypatch)
        h = {"Authorization": f"Bearer {tokens['access_token']}"}
        r = c.get("/api/v1/auth/whoami", headers=h)
        assert r.status_code == 200 and r.json()["username"] == "v2user"
        # 未登录 401
        assert c.get("/api/v1/auth/whoami").status_code == 401


def test_submit_and_status(monkeypatch):
    monkeypatch.setattr(
        "app.routers.public.domain_checks_cached",
        lambda domain: {"dns_resolves": True, "https_reachable": True, "tls_ok": True, "error": None},
    )
    with TestClient(app) as c:
        _register(c, "submituser", "submit@example.com", monkeypatch)
        h = _auth_headers(c, "submituser")
        r = c.post("/api/v1/submissions", json={"domain": "submit-demo.example", "organization": "X"}, headers=h)
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "pending" and r.json()["registry_type"] == "free"

        r = c.get("/api/v1/status/submit-demo.example")
        assert r.json()["status"] == "pending"

        r = c.get("/api/v1/me/domains", headers=h)
        assert r.status_code == 200 and any(d["domain"] == "submit-demo.example" for d in r.json())


def test_ownership_verify(monkeypatch):
    monkeypatch.setattr(
        "app.routers.public.domain_checks_cached",
        lambda domain: {"dns_resolves": True, "https_reachable": True, "tls_ok": True, "error": None},
    )
    with TestClient(app) as c:
        _register(c, "owneruser", "owner@example.com", monkeypatch)
        h = _auth_headers(c, "owneruser")
        c.post("/api/v1/submissions", json={"domain": "owner-demo.example", "organization": "X"}, headers=h)

        monkeypatch.setattr("app.services.reputation.check_dns_txt", lambda domain, token: False)
        r = c.post("/api/v1/ownership/verify", json={"domain": "owner-demo.example"}, headers=h)
        assert r.status_code == 400

        monkeypatch.setattr("app.services.reputation.check_dns_txt", lambda domain, token: True)
        r = c.post("/api/v1/ownership/verify", json={"domain": "owner-demo.example"}, headers=h)
        assert r.status_code == 200 and r.json()["verification_level"] >= 1


def test_admin_ops(monkeypatch):
    monkeypatch.setattr(
        "app.routers.public.domain_checks_cached",
        lambda domain: {"dns_resolves": True, "https_reachable": True, "tls_ok": True, "error": None},
    )
    with TestClient(app) as pub, TestClient(admin_app) as adm:
        _register(pub, "plainuser", "plain@example.com", monkeypatch)
        h = _auth_headers(pub, "plainuser")
        pub.post("/api/v1/submissions", json={"domain": "admin-demo.example", "organization": "X"}, headers=h)

        # 普通用户访问管理 API -> 403
        assert adm.get("/api/v1/admin/domains", headers=h).status_code == 403

        # 管理员登录（自动建档）
        r = adm.post("/api/v1/admin/login", json={"username": "admin", "password": "change-me-in-production"})
        assert r.status_code == 200, r.text
        ah = {"Authorization": f"Bearer {r.json()['access_token']}"}

        rows = adm.get("/api/v1/admin/domains", params={"status": "pending"}, headers=ah).json()
        did = next(d["id"] for d in rows if d["domain"] == "admin-demo.example")

        r = adm.post(f"/api/v1/admin/domains/{did}/verify", json={}, headers=ah)
        assert r.status_code == 200 and r.json()["verification_level"] == 3

        r = adm.post(f"/api/v1/admin/domains/{did}/set-type", json={"registry_type": "official"}, headers=ah)
        assert r.json()["verification_level"] == 3, "设为官方不应自动授予 L4"

        r = adm.post(f"/api/v1/admin/domains/{did}/confirm-official", json={}, headers=ah)
        assert r.json()["official_verified"] is True and r.json()["verification_level"] == 4

        r = adm.post(f"/api/v1/admin/domains/{did}/set-category", json={"category": "ai"}, headers=ah)
        assert r.json()["category"] == "ai"

        r = adm.post(f"/api/v1/admin/domains/{did}/revoke", json={"reason": "test"}, headers=ah)
        assert r.json()["status"] == "revoked"

        r = adm.post(f"/api/v1/admin/domains/{did}/delete", json={}, headers=ah)
        assert r.status_code == 200 and r.json()["deleted"] is True


def test_admin_users_and_batch(monkeypatch):
    with TestClient(app) as pub, TestClient(admin_app) as adm:
        _register(pub, "batchuser", "batch@example.com", monkeypatch)
        r = adm.post("/api/v1/admin/login", json={"username": "admin", "password": "change-me-in-production"})
        ah = {"Authorization": f"Bearer {r.json()['access_token']}"}

        users = adm.get("/api/v1/admin/users", params={"q": "batchuser"}, headers=ah).json()
        assert users and users[0]["username"] == "batchuser"
        uid = users[0]["id"]

        # 空理由 400
        assert adm.post(f"/api/v1/admin/users/{uid}/remove", json={"reason": " "}, headers=ah).status_code == 400
        r = adm.post(f"/api/v1/admin/users/{uid}/remove", json={"reason": "测试移除"}, headers=ah)
        assert r.status_code == 200 and r.json()["removed"] is True
