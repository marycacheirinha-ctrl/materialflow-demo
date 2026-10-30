"""Estrutura inicial: contas, sessões, auditoria, categorias e solicitações de material.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

DT = sa.DateTime(timezone=True)


def _pk(table: str) -> sa.PrimaryKeyConstraint:
    return sa.PrimaryKeyConstraint("id", name=f"pk_{table}")


def _fk(table: str, column: str, ref: str, *, ondelete: str | None = None) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column], [f"{ref}.id"], name=f"fk_{table}_{column}_{ref}", ondelete=ondelete
    )


def _uq(table: str, *columns: str) -> sa.UniqueConstraint:
    return sa.UniqueConstraint(*columns, name=f"uq_{table}_{columns[0]}")


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("department", sa.String(40)),
        sa.Column("is_admin", sa.Boolean, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("must_change_password", sa.Boolean, nullable=False),
        sa.Column("password_changed_at", DT),
        sa.Column("last_login_at", DT),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        _pk("users"),
        _uq("users", "username"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("last_seen_at", DT, nullable=False),
        sa.Column("expires_at", DT, nullable=False),
        sa.Column("revoked_at", DT),
        _pk("user_sessions"),
        _fk("user_sessions", "user_id", "users", ondelete="CASCADE"),
        _uq("user_sessions", "token_hash"),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("expires_at", DT, nullable=False),
        sa.Column("used_at", DT),
        sa.Column("issued_by_id", sa.Integer),
        _pk("password_reset_tokens"),
        _fk("password_reset_tokens", "user_id", "users", ondelete="CASCADE"),
        _fk("password_reset_tokens", "issued_by_id", "users", ondelete="SET NULL"),
        _uq("password_reset_tokens", "token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("username", sa.String(150), nullable=False),
        sa.Column("succeeded", sa.Boolean, nullable=False),
        sa.Column("attempted_at", DT, nullable=False),
        _pk("login_attempts"),
    )
    op.create_index("ix_login_attempts_username", "login_attempts", ["username"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("occurred_at", DT, nullable=False),
        sa.Column("user_id", sa.Integer),
        sa.Column("username", sa.String(64)),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40)),
        sa.Column("entity_id", sa.String(40)),
        sa.Column("details", sa.JSON),
        _pk("audit_log"),
        _fk("audit_log", "user_id", "users", ondelete="SET NULL"),
    )
    op.create_index("ix_audit_log_occurred_at", "audit_log", ["occurred_at"])
    op.create_index("ix_audit_log_action", "audit_log", ["action"])

    op.create_table(
        "component_categories",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name_pt", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        _pk("component_categories"),
        _uq("component_categories", "code"),
    )

    op.create_table(
        "category_fields",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("category_id", sa.Integer, nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("sort_order", sa.Integer, nullable=False),
        _pk("category_fields"),
        _fk("category_fields", "category_id", "component_categories", ondelete="CASCADE"),
        sa.UniqueConstraint("category_id", "label", name="uq_category_fields_category_label"),
    )
    op.create_index("ix_category_fields_category_id", "category_fields", ["category_id"])

    op.create_table(
        "material_requests",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("internal_code", sa.String(20)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("created_by_id", sa.Integer, nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        sa.Column("submitted_at", DT),
        sa.Column("original_description", sa.Text, nullable=False),
        sa.Column("category_id", sa.Integer),
        sa.Column("brand", sa.String(100)),
        sa.Column("model", sa.String(100)),
        sa.Column("manufacturer_reference", sa.String(100)),
        sa.Column("description_pt", sa.String(40)),
        sa.Column("description_en", sa.String(40)),
        sa.Column("net_weight", sa.Numeric(14, 4)),
        sa.Column("gross_weight", sa.Numeric(14, 4)),
        sa.Column("weight_unit", sa.String(10)),
        sa.Column("length", sa.Numeric(14, 3)),
        sa.Column("width", sa.Numeric(14, 3)),
        sa.Column("height", sa.Numeric(14, 3)),
        sa.Column("dimension_unit", sa.String(10)),
        sa.Column("base_unit", sa.String(10)),
        sa.Column("sap_material_code", sa.String(40)),
        sa.Column("sap_material_type", sa.String(10)),
        sa.Column("sap_material_group", sa.String(20)),
        sa.Column("sap_plant", sa.String(10)),
        sa.Column("sap_purchasing_org", sa.String(10)),
        _pk("material_requests"),
        _fk("material_requests", "created_by_id", "users"),
        _fk("material_requests", "category_id", "component_categories"),
        _uq("material_requests", "internal_code"),
        sa.UniqueConstraint("sap_material_code", name="uq_material_requests_sap_material_code"),
    )
    op.create_index("ix_material_requests_status", "material_requests", ["status"])
    op.create_index("ix_material_requests_created_by_id", "material_requests", ["created_by_id"])

    op.create_table(
        "material_characteristics",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("request_id", sa.Integer, nullable=False),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("value", sa.String(255)),
        sa.Column("unit", sa.String(20)),
        sa.Column("source", sa.String(40)),
        sa.Column("sort_order", sa.Integer, nullable=False),
        _pk("material_characteristics"),
        _fk("material_characteristics", "request_id", "material_requests", ondelete="CASCADE"),
    )
    op.create_index("ix_material_characteristics_request_id", "material_characteristics", ["request_id"])

    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("request_id", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(64), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer, nullable=False),
        sa.Column("uploaded_at", DT, nullable=False),
        _pk("attachments"),
        _fk("attachments", "request_id", "material_requests", ondelete="CASCADE"),
        _fk("attachments", "uploaded_by_id", "users"),
        _uq("attachments", "storage_key"),
        sa.UniqueConstraint("request_id", "sha256", name="uq_attachments_request_sha256"),
    )
    op.create_index("ix_attachments_request_id", "attachments", ["request_id"])

    op.create_table(
        "supplier_offers",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("request_id", sa.Integer, nullable=False),
        sa.Column("supplier_name", sa.String(150), nullable=False),
        sa.Column("supplier_reference", sa.String(100)),
        sa.Column("purchase_price", sa.Numeric(18, 4)),
        sa.Column("currency", sa.String(3)),
        sa.Column("purchase_unit", sa.String(10)),
        sa.Column("quantity_per_package", sa.Numeric(14, 3)),
        sa.Column("price_valid_until", sa.Date),
        sa.Column("price_reference", sa.String(100)),
        sa.Column("notes", sa.String(255)),
        sa.Column("created_by_id", sa.Integer, nullable=False),
        sa.Column("created_at", DT, nullable=False),
        sa.Column("updated_at", DT, nullable=False),
        _pk("supplier_offers"),
        _fk("supplier_offers", "request_id", "material_requests", ondelete="CASCADE"),
        _fk("supplier_offers", "created_by_id", "users"),
    )
    op.create_index("ix_supplier_offers_request_id", "supplier_offers", ["request_id"])

    op.create_table(
        "request_history",
        sa.Column("id", sa.Integer, nullable=False),
        sa.Column("request_id", sa.Integer, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("occurred_at", DT, nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("from_status", sa.String(40)),
        sa.Column("to_status", sa.String(40), nullable=False),
        sa.Column("note", sa.Text),
        sa.Column("changes", sa.JSON),
        _pk("request_history"),
        _fk("request_history", "request_id", "material_requests", ondelete="CASCADE"),
        _fk("request_history", "user_id", "users"),
    )
    op.create_index("ix_request_history_request_id", "request_history", ["request_id"])


def downgrade() -> None:
    for table in (
        "request_history",
        "supplier_offers",
        "attachments",
        "material_characteristics",
        "material_requests",
        "category_fields",
        "component_categories",
        "audit_log",
        "login_attempts",
        "password_reset_tokens",
        "user_sessions",
        "users",
    ):
        op.drop_table(table)
