from datetime import datetime

from pydantic import BaseModel, Field, field_validator
import ipaddress
import re

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)


class DomainSubmit(BaseModel):
    domain: str = Field(min_length=3, max_length=253)
    organization: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=80)
    submitter_email: str | None = Field(default=None, max_length=320)
    ownership_method: str = Field(default="dns_txt", pattern="^(dns_txt|well_known)$")
    registry_type: str = Field(default="free", pattern="^(official|free)$")
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str) -> str:
        value = value.strip().lower().rstrip(".")
        if value.startswith("http://") or value.startswith("https://") or "/" in value:
            raise ValueError("只提交纯域名，例如 example.com")
        if value == "localhost" or value.endswith(".localhost"):
            raise ValueError("不允许提交本机地址（localhost）")
        try:
            ipaddress.ip_address(value)
            is_ip = True
        except ValueError:
            is_ip = False
        if is_ip:
            raise ValueError("不允许提交 IP 地址")
        if not DOMAIN_RE.match(value):
            raise ValueError("域名格式无效")
        return value


class DomainOut(BaseModel):
    id: int
    domain: str
    organization: str
    category: str | None
    status: str
    verification_level: int
    registry_type: str
    requested_type: str = "free"
    ownership_verified: bool = False
    official_verified: bool = False

    model_config = {"from_attributes": True}


class DomainSubmitOut(DomainOut):
    verification_token: str


class AuditLogOut(BaseModel):
    action: str
    actor: str
    detail: str | None
    created_at: datetime | None


class AdminDomainOut(DomainOut):
    notes: str | None = None
    submitter_username: str | None = None
    submitter_email: str | None = None
    created_at: datetime | None = None
    audit_logs: list[AuditLogOut] = []


class AdminQueueOut(BaseModel):
    items: list[AdminDomainOut]
    total: int
    page: int
    page_size: int
    total_pages: int


class EmailUpdate(BaseModel):
    email: str = Field(max_length=320)
    code: str = Field(min_length=6, max_length=6)
    email_token: str


class OwnershipVerify(BaseModel):
    domain: str = Field(min_length=3, max_length=253)


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=32)
    password: str = Field(min_length=8, max_length=128)
    email: str = Field(max_length=320)
    code: str = Field(min_length=6, max_length=6)
    email_token: str


class LoginIn(BaseModel):
    username: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ApiKeyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class ApiKeyOut(BaseModel):
    id: int
    name: str
    created_at: str
    last_used_at: str | None
    revoked: bool


class ApiKeyCreated(ApiKeyOut):
    key: str
