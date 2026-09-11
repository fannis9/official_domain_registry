import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_api_keys_flow(monkeypatch):
    from tests.test_api import _fake_captcha, _register  # noqa: F401

    monkeypatch.setattr(
        "app.services.verification.send_verification_email",
        lambda to, code: None,
    )
    monkeypatch.setattr("app.services.verification.issue_captcha", _fake_captcha)

    with TestClient(app) as c:
        tokens = _register(c, "keyuser", "key@example.com", monkeypatch)
        h = {"Authorization": f"Bearer {tokens['access_token']}"}

        # 创建 API Key
        r = c.post("/api/v1/me/api-keys", json={"name": "plugin"}, headers=h)
        assert r.status_code == 201, r.text
        key = r.json()["key"]
        assert key.startswith("odrk.")

        # 用 API Key 认证
        kh = {"Authorization": f"Bearer {key}"}
        r = c.get("/api/v1/auth/whoami", headers=kh)
        assert r.status_code == 200 and r.json()["username"] == "keyuser"

        # 列表
        r = c.get("/api/v1/me/api-keys", headers=h)
        assert r.status_code == 200 and len(r.json()) == 1

        # 吊销后失效
        kid = r.json()[0]["id"]
        assert c.post(f"/api/v1/me/api-keys/{kid}/revoke", json={}, headers=h).status_code == 200
        assert c.get("/api/v1/auth/whoami", headers=kh).status_code == 401
