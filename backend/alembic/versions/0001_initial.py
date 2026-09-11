"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-11
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("domain", sa.String(253), nullable=False),
        sa.Column("organization", sa.String(200), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("registry_type", sa.String(20), nullable=False, server_default="free"),
        sa.Column("verification_level", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verification_token", sa.String(128), nullable=True),
        sa.Column("verification_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ownership_method", sa.String(30), nullable=True),
        sa.Column("submitter_email", sa.String(320), nullable=True),
        sa.Column("submitter_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("ownership_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("official_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requested_type", sa.String(20), nullable=False, server_default="free"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("domain", name="uq_domains_domain"),
    )
    op.create_index("ix_domains_domain", "domains", ["domain"])
    op.create_index("ix_domains_status", "domains", ["status"])
    op.create_index("ix_domains_registry_type", "domains", ["registry_type"])
    op.create_index("ix_domains_submitter_id", "domains", ["submitter_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id"), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("actor", sa.String(200), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_domain_id", "audit_logs", ["domain_id"])

    op.create_table(
        "submission_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_submission_attempts_ip_hash", "submission_attempts", ["ip_hash"])

    op.create_table(
        "rate_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ip_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rate_attempts_ip_hash", "rate_attempts", ["ip_hash"])
    op.create_index("ix_rate_attempts_action", "rate_attempts", ["action"])

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])


def downgrade() -> None:
    op.drop_table("api_keys")
    op.drop_table("rate_attempts")
    op.drop_table("submission_attempts")
    op.drop_table("audit_logs")
    op.drop_table("domains")
    op.drop_table("users")
