"""Regras de visibilidade e de edição, em função do departamento e do estado."""

from app.domain.enums import RequestStatus
from app.domain.permissions import Actor, Permission, has_permission
from app.domain.workflow import (
    COMMERCIAL_EDITABLE_STATUSES,
    SAP_EDITABLE_STATUSES,
    TECHNICIAN_EDITABLE_STATUSES,
)


def can_view_request(actor: Actor, *, status: RequestStatus, created_by_id: int) -> bool:
    """Técnicos veem as suas; Compras e Dados Mestre veem as submetidas (nunca rascunhos)."""
    if has_permission(actor, Permission.REQUEST_VIEW_SUBMITTED) and status != RequestStatus.RASCUNHO:
        return True
    return has_permission(actor, Permission.REQUEST_VIEW_OWN) and created_by_id == actor.id


def can_edit_technical(actor: Actor, *, status: RequestStatus, created_by_id: int) -> bool:
    return (
        has_permission(actor, Permission.REQUEST_EDIT_TECHNICAL)
        and created_by_id == actor.id
        and status in TECHNICIAN_EDITABLE_STATUSES
    )


def can_edit_commercial(actor: Actor, *, status: RequestStatus) -> bool:
    return has_permission(actor, Permission.COMMERCIAL_EDIT) and status in COMMERCIAL_EDITABLE_STATUSES


def can_edit_sap_fields(actor: Actor, *, status: RequestStatus) -> bool:
    return has_permission(actor, Permission.MASTERDATA_EDIT_SAP_FIELDS) and status in SAP_EDITABLE_STATUSES
