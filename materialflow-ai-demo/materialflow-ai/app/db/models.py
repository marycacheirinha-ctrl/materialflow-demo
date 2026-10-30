"""Modelos SQLAlchemy. Os enums são guardados como texto (sem tipos nativos) para facilitar migrações."""

import datetime as dt
from decimal import Decimal

from sqlalchemy import JSON, Boolean, Date, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import UTCDateTime
from app.domain.enums import (
    AttachmentKind,
    CharacteristicSource,
    Department,
    HistoryEvent,
    RequestStatus,
)
from app.utils import clock


def _now() -> dt.datetime:
    return clock.now()


def _enum(enum_class: type) -> Enum:
    return Enum(enum_class, native_enum=False, length=40, validate_strings=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    department: Mapped[Department | None] = mapped_column(_enum(Department))
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    last_login_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now, onupdate=_now)


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    last_seen_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    expires_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    revoked_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)


class PasswordResetToken(Base):
    """`used_at` marca o token como consumido ou invalidado."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    expires_at: Mapped[dt.datetime] = mapped_column(UTCDateTime)
    used_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)
    issued_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(150), index=True)
    succeeded: Mapped[bool] = mapped_column(Boolean)
    attempted_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    occurred_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(40))
    details: Mapped[dict | None] = mapped_column(JSON)


class ComponentCategory(Base):
    __tablename__ = "component_categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name_pt: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    fields: Mapped[list["CategoryField"]] = relationship(
        back_populates="category", cascade="all, delete-orphan", order_by="CategoryField.sort_order"
    )


class CategoryField(Base):
    """Campo técnico sugerido para uma categoria (sem valores)."""

    __tablename__ = "category_fields"
    __table_args__ = (UniqueConstraint("category_id", "label", name="uq_category_fields_category_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("component_categories.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    sort_order: Mapped[int] = mapped_column(default=0)

    category: Mapped["ComponentCategory"] = relationship(back_populates="fields")


class MaterialRequest(Base):
    __tablename__ = "material_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    internal_code: Mapped[str | None] = mapped_column(String(20), unique=True)
    status: Mapped[RequestStatus] = mapped_column(_enum(RequestStatus), default=RequestStatus.RASCUNHO, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    submitted_at: Mapped[dt.datetime | None] = mapped_column(UTCDateTime)

    original_description: Mapped[str] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("component_categories.id"))
    brand: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(100))
    manufacturer_reference: Mapped[str | None] = mapped_column(String(100))

    description_pt: Mapped[str | None] = mapped_column(String(40))
    description_en: Mapped[str | None] = mapped_column(String(40))

    net_weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    gross_weight: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    weight_unit: Mapped[str | None] = mapped_column(String(10))
    length: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    width: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    height: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    dimension_unit: Mapped[str | None] = mapped_column(String(10))
    base_unit: Mapped[str | None] = mapped_column(String(10))

    # O código SAP nunca é gerado automaticamente; fica vazio até à criação efetiva.
    sap_material_code: Mapped[str | None] = mapped_column(String(40), unique=True)
    sap_material_type: Mapped[str | None] = mapped_column(String(10))
    sap_material_group: Mapped[str | None] = mapped_column(String(20))
    sap_plant: Mapped[str | None] = mapped_column(String(10))
    sap_purchasing_org: Mapped[str | None] = mapped_column(String(10))

    category: Mapped["ComponentCategory | None"] = relationship()
    created_by: Mapped["User"] = relationship(foreign_keys=[created_by_id])
    characteristics: Mapped[list["MaterialCharacteristic"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="MaterialCharacteristic.sort_order"
    )
    attachments: Mapped[list["Attachment"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="Attachment.id"
    )
    offers: Mapped[list["SupplierOffer"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="SupplierOffer.id"
    )
    history: Mapped[list["RequestHistory"]] = relationship(
        back_populates="request", cascade="all, delete-orphan", order_by="RequestHistory.id"
    )


class MaterialCharacteristic(Base):
    """Valor vazio significa «não identificado». A origem é obrigatória quando há valor."""

    __tablename__ = "material_characteristics"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("material_requests.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    value: Mapped[str | None] = mapped_column(String(255))
    unit: Mapped[str | None] = mapped_column(String(20))
    source: Mapped[CharacteristicSource | None] = mapped_column(_enum(CharacteristicSource))
    sort_order: Mapped[int] = mapped_column(default=0)

    request: Mapped["MaterialRequest"] = relationship(back_populates="characteristics")


class Attachment(Base):
    __tablename__ = "attachments"
    __table_args__ = (UniqueConstraint("request_id", "sha256", name="uq_attachments_request_sha256"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("material_requests.id", ondelete="CASCADE"), index=True)
    kind: Mapped[AttachmentKind] = mapped_column(_enum(AttachmentKind))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int]
    sha256: Mapped[str] = mapped_column(String(64))
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)
    uploaded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)

    request: Mapped["MaterialRequest"] = relationship(back_populates="attachments")
    uploaded_by: Mapped["User"] = relationship()


class SupplierOffer(Base):
    __tablename__ = "supplier_offers"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("material_requests.id", ondelete="CASCADE"), index=True)
    supplier_name: Mapped[str] = mapped_column(String(150))
    supplier_reference: Mapped[str | None] = mapped_column(String(100))
    purchase_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    purchase_unit: Mapped[str | None] = mapped_column(String(10))
    quantity_per_package: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    price_valid_until: Mapped[dt.date | None] = mapped_column(Date)
    price_reference: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(String(255))
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)

    request: Mapped["MaterialRequest"] = relationship(back_populates="offers")


class RequestHistory(Base):
    __tablename__ = "request_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("material_requests.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    occurred_at: Mapped[dt.datetime] = mapped_column(UTCDateTime, default=_now)
    event_type: Mapped[HistoryEvent] = mapped_column(_enum(HistoryEvent))
    from_status: Mapped[RequestStatus | None] = mapped_column(_enum(RequestStatus))
    to_status: Mapped[RequestStatus] = mapped_column(_enum(RequestStatus))
    note: Mapped[str | None] = mapped_column(Text)
    changes: Mapped[dict | None] = mapped_column(JSON)

    request: Mapped["MaterialRequest"] = relationship(back_populates="history")
    user: Mapped["User"] = relationship()
