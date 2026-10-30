"""Máquina de estados das solicitações: Técnicos / Logística, Compras, Dados Mestre.

Só Dados Mestre aprova, exporta para o SAP e conclui.
"""

from dataclasses import dataclass

from app.domain.enums import RequestStatus
from app.domain.permissions import Permission

S = RequestStatus


@dataclass(frozen=True)
class Transition:
    source: RequestStatus
    target: RequestStatus
    permission: Permission
    label: str
    requires_note: bool = False
    owner_only: bool = False


TRANSITIONS: tuple[Transition, ...] = (
    Transition(S.RASCUNHO, S.PENDENTE_COMPRAS, Permission.REQUEST_SUBMIT, "Submeter a Compras", owner_only=True),
    Transition(
        S.DEVOLVIDO_PARA_CORRECAO, S.PENDENTE_COMPRAS, Permission.REQUEST_SUBMIT, "Reenviar a Compras", owner_only=True
    ),
    Transition(
        S.PENDENTE_COMPRAS, S.PENDENTE_DADOS_MESTRE, Permission.PURCHASING_FORWARD, "Encaminhar para Dados Mestre"
    ),
    Transition(
        S.PENDENTE_COMPRAS, S.DEVOLVIDO_PARA_CORRECAO, Permission.PURCHASING_RETURN, "Devolver para correção", requires_note=True
    ),
    Transition(
        S.PENDENTE_DADOS_MESTRE,
        S.DEVOLVIDO_PARA_CORRECAO,
        Permission.MASTERDATA_RETURN,
        "Devolver para correção",
        requires_note=True,
    ),
    Transition(S.PENDENTE_DADOS_MESTRE, S.APROVADO_PARA_SAP, Permission.MASTERDATA_APPROVE, "Aprovar para SAP"),
    Transition(S.APROVADO_PARA_SAP, S.CONCLUIDO_NO_SAP, Permission.MASTERDATA_REGISTER_SAP_CODE, "Concluir no SAP"),
)

TECHNICIAN_EDITABLE_STATUSES = frozenset({S.RASCUNHO, S.DEVOLVIDO_PARA_CORRECAO})
COMMERCIAL_EDITABLE_STATUSES = frozenset({S.PENDENTE_COMPRAS})
SAP_EDITABLE_STATUSES = frozenset({S.PENDENTE_DADOS_MESTRE})


def find_transition(source: RequestStatus, target: RequestStatus) -> Transition | None:
    for transition in TRANSITIONS:
        if transition.source == source and transition.target == target:
            return transition
    return None


def transitions_from(source: RequestStatus) -> list[Transition]:
    return [t for t in TRANSITIONS if t.source == source]
