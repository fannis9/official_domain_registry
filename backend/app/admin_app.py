from fastapi import FastAPI

from app.config import assert_safe_settings, settings
from app.routers import admin

assert_safe_settings()

admin_app = FastAPI(title=f"{settings.app_name} Admin API", version="2.0.0")


@admin_app.get("/api/v1/healthz")
async def healthz():
    return {"status": "ok"}


admin_app.include_router(admin.router)
