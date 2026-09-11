from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Official Domain Registry"
    environment: str = "development"  # development | staging | production

    database_url: str = "sqlite+aiosqlite:///./registry.db"
    database_echo: bool = False

    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 30

    api_key_prefix: str = "odrk"

    admin_username: str = "admin"
    admin_password: str = "change-me-in-production"

    verification_ttl_minutes: int = 60
    rate_limit_per_minute: int = 30

    smtp_host: str = ""
    smtp_port: int = 465
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    cors_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()


def assert_safe_settings():
    if settings.is_production:
        if settings.jwt_secret == "change-me-in-production":
            raise RuntimeError("生产模式拒绝启动：JWT_SECRET 未设置")
        if settings.admin_password == "change-me-in-production":
            raise RuntimeError("生产模式拒绝启动：ADMIN_PASSWORD 未设置")
    elif settings.jwt_secret == "change-me-in-production":
        print("[WARN] 使用默认 JWT_SECRET，生产环境请务必修改")
