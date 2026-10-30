"""Registo de auditoria. Nunca guardar palavras-passe, tokens nem conteúdo de documentos."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditLog
from app.domain.errors import PermissionDenied
from app.domain.permissions import Actor, Permission, require_permission
from app.domain.serialization import jsonable
from app.utils import clock


def record(
    session: Session,
    action: str,
    *,
    actor: Actor | None = None,
    username: str | None = None,
    entity_type: str | None = None,
    entity_id: int | str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    session.add(
        AuditLog(
            occurred_at=clock.now(),
            user_id=actor.id if actor else None,
            username=(actor.username if actor else username),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            details=jsonable(details) if details else None,
        )
    )


def list_entries(session: Session, actor: Actor, *, limit: int = 200, action: str | None = None) -> list[AuditLog]:
    require_permission(actor, Permission.VIEW_AUDIT_LOG)
    if limit < 1 or limit > 1000:
        raise PermissionDenied("Limite inválido.")
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    return list(session.scalars(stmt))
