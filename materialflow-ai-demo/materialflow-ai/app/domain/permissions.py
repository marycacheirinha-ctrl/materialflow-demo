"""Permissões por departamento. A verificação é feita sempre no servidor, nos serviços."""

from enum import StrEnum
from typing import Protocol

from app.domain.enums import Department
from app.domain.errors import PermissionDenied


class Actor(Protocol):
    id: int
    username: str
    department: Department | None
    is_admin: bool


class Permission(StrEnum):
    MANAGE_USERS = "MANAGE_USERS"
    VIEW_AUDIT_LOG = "VIEW_AUDIT_LOG"
    REQUEST_VIEW_OWN = "REQUEST_VIEW_OWN"
    REQUEST_VIEW_SUBMITTED = "REQUEST_VIEW_SUBMITTED"
    REQUEST_CREATE = "REQUEST_CREATE"
    REQUEST_EDIT_TECHNICAL = "REQUEST_EDIT_TECHNICAL"
    REQUEST_SUBMIT = "REQUEST_SUBMIT"
    COMMERCIAL_EDIT = "COMMERCIAL_EDIT"
    PURCHASING_RETURN = "PURCHASING_RETURN"
    PURCHASING_FORWARD = "PURCHASING_FORWARD"
    MASTERDATA_EDIT_SAP_FIELDS = "MASTERDATA_EDIT_SAP_FIELDS"
    MASTERDATA_RETURN = "MASTERDATA_RETURN"
    MASTERDATA_APPROVE = "MASTERDATA_APPROVE"
    MASTERDATA_REGISTER_SAP_CODE = "MASTERDATA_REGISTER_SAP_CODE"
    MASTERDATA_EXPORT_SAP = "MASTERDATA_EXPORT_SAP"


P = Permission

DEPARTMENT_PERMISSIONS: dict[Department, frozenset[Permission]] = {
    Department.TECNICOS_LOGISTICA: frozenset(
        {P.REQUEST_VIEW_OWN, P.REQUEST_CREATE, P.REQUEST_EDIT_TECHNICAL, P.REQUEST_SUBMIT}
    ),
    Department.COMPRAS: frozenset(
        {P.REQUEST_VIEW_SUBMITTED, P.COMMERCIAL_EDIT, P.PURCHASING_RETURN, P.PURCHASING_FORWARD}
    ),
    Department.DADOS_MESTRE: frozenset(
        {
            P.REQUEST_VIEW_SUBMITTED,
            P.MASTERDATA_EDIT_SAP_FIELDS,
            P.MASTERDATA_RETURN,
            P.MASTERDATA_APPROVE,
            P.MASTERDATA_REGISTER_SAP_CODE,
            P.MASTERDATA_EXPORT_SAP,
        }
    ),
}

# O administrador técnico gere contas e consulta a auditoria, sem autoridade sobre materiais.
ADMIN_PERMISSIONS: frozenset[Permission] = frozenset({P.MANAGE_USERS, P.VIEW_AUDIT_LOG})


def permissions_for(actor: Actor) -> frozenset[Permission]:
    granted: set[Permission] = set()
    if actor.department is not None:
        granted |= DEPARTMENT_PERMISSIONS[actor.department]
    if actor.is_admin:
        granted |= ADMIN_PERMISSIONS
    return frozenset(granted)


def has_permission(actor: Actor, permission: Permission) -> bool:
    return permission in permissions_for(actor)


def require_permission(actor: Actor, permission: Permission, message: str | None = None) -> None:
    if not has_permission(actor, permission):
        raise PermissionDenied(message or "Não tem permissão para executar esta operação.")
