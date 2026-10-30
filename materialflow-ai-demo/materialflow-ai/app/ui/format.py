"""Formatação de valores para apresentação em português de Portugal."""

import datetime as dt
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.domain.enums import RequestStatus
from app.domain.labels import STATUS_LABELS
from app.domain.numbers import format_decimal

LISBON = ZoneInfo("Europe/Lisbon")


def fmt_dt(value: dt.datetime | None) -> str:
    if value is None:
        return ""
    return value.astimezone(LISBON).strftime("%d/%m/%Y %H:%M")


def fmt_date(value: dt.date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else ""


def fmt_dec(value: Decimal | None) -> str:
    return format_decimal(value)


def dash(value: object) -> str:
    return "—" if value in (None, "") else str(value)


_STATUS_CLASS = {
    RequestStatus.RASCUNHO: "mf-draft",
    RequestStatus.PENDENTE_COMPRAS: "mf-pending",
    RequestStatus.PENDENTE_DADOS_MESTRE: "mf-pending",
    RequestStatus.DEVOLVIDO_PARA_CORRECAO: "mf-returned",
    RequestStatus.APROVADO_PARA_SAP: "mf-approved",
    RequestStatus.CONCLUIDO_NO_SAP: "mf-done",
}


def status_badge(status: RequestStatus) -> str:
    """HTML de um selo de estado. Só usa texto fixo da aplicação, nunca texto do utilizador."""
    return f'<span class="mf-badge {_STATUS_CLASS[status]}">{STATUS_LABELS[status]}</span>'
