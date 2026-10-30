"""Solicitações de material: criação, edição por departamento, anexos e workflow.

Todas as funções verificam as permissões no servidor. Nenhuma faz commit: quem chama
usa `session_scope()`.
"""

from collections.abc import Mapping
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db.models import (
    Attachment,
    ComponentCategory,
    MaterialCharacteristic,
    MaterialRequest,
    RequestHistory,
    SupplierOffer,
)
from app.domain import access
from app.domain.descriptors import check_descriptor
from app.domain.enums import AttachmentKind, CharacteristicSource, HistoryEvent, RequestStatus
from app.domain.errors import ConflictError, NotFoundError, PermissionDenied, ValidationError
from app.domain.numbers import parse_decimal
from app.domain.permissions import Permission, require_permission
from app.domain.serialization import jsonable
from app.domain.validation import clean_text
from app.domain.workflow import find_transition
from app.security.uploads import validate_upload
from app.services import audit, storage
from app.services.dto import CurrentUser
from app.utils import clock

# Campos SAP obrigatórios para aprovar. Serão configuráveis a partir do template real de Dados Mestre.
REQUIRED_SAP_FIELDS: dict[str, str] = {
    "sap_material_type": "Tipo de material",
    "sap_material_group": "Grupo de mercadorias",
    "base_unit": "Unidade base",
    "sap_plant": "Centro",
    "sap_purchasing_org": "Organização de compras",
}

_DECIMAL_FIELDS = {
    "net_weight": "Peso líquido unitário",
    "gross_weight": "Peso bruto",
    "length": "Comprimento",
    "width": "Largura",
    "height": "Altura",
}
_TEXT_FIELDS = {
    "original_description": ("Descrição original", 2000),
    "brand": ("Marca", 100),
    "model": ("Modelo", 100),
    "manufacturer_reference": ("Referência do fabricante", 100),
    "weight_unit": ("Unidade de peso", 10),
    "dimension_unit": ("Unidade de medida", 10),
    "base_unit": ("Unidade base", 10),
}
TECHNICAL_FIELDS = (
    set(_TEXT_FIELDS) | set(_DECIMAL_FIELDS) | {"category_id", "description_pt", "description_en"}
)
SAP_FIELDS = {
    "sap_material_type": ("Tipo de material", 10),
    "sap_material_group": ("Grupo de mercadorias", 20),
    "sap_plant": ("Centro", 10),
    "sap_purchasing_org": ("Organização de compras", 10),
    "base_unit": ("Unidade base", 10),
}


# ---------------------------------------------------------------- leitura

def _load_options():
    return (
        selectinload(MaterialRequest.characteristics),
        selectinload(MaterialRequest.attachments),
        selectinload(MaterialRequest.offers),
        selectinload(MaterialRequest.history).selectinload(RequestHistory.user),
        selectinload(MaterialRequest.category),
        selectinload(MaterialRequest.created_by),
    )


def get_request(session: Session, actor: CurrentUser, request_id: int, *, for_update: bool = False) -> MaterialRequest:
    stmt = select(MaterialRequest).where(MaterialRequest.id == request_id).options(*_load_options())
    if for_update:
        stmt = stmt.with_for_update()
    req = session.scalar(stmt)
    if req is None or not access.can_view_request(actor, status=req.status, created_by_id=req.created_by_id):
        # Mesma mensagem nos dois casos: não revelar a existência de solicitações alheias.
        raise NotFoundError("Solicitação não encontrada.")
    return req


def list_requests(
    session: Session, actor: CurrentUser, *, status: RequestStatus | None = None, search: str | None = None, limit: int = 200
) -> list[MaterialRequest]:
    stmt = select(MaterialRequest).options(selectinload(MaterialRequest.category), selectinload(MaterialRequest.created_by))
    from app.domain.permissions import has_permission

    sees_submitted = has_permission(actor, Permission.REQUEST_VIEW_SUBMITTED)
    sees_own = has_permission(actor, Permission.REQUEST_VIEW_OWN)
    if sees_submitted and sees_own:
        stmt = stmt.where(
            or_(MaterialRequest.status != RequestStatus.RASCUNHO, MaterialRequest.created_by_id == actor.id)
        )
    elif sees_submitted:
        stmt = stmt.where(MaterialRequest.status != RequestStatus.RASCUNHO)
    elif sees_own:
        stmt = stmt.where(MaterialRequest.created_by_id == actor.id)
    else:
        return []
    if status is not None:
        stmt = stmt.where(MaterialRequest.status == status)
    term = (search or "").strip()
    if term:
        like = f"%{term}%"
        stmt = stmt.where(
            or_(
                MaterialRequest.internal_code.ilike(like),
                MaterialRequest.original_description.ilike(like),
                MaterialRequest.description_pt.ilike(like),
                MaterialRequest.description_en.ilike(like),
                MaterialRequest.manufacturer_reference.ilike(like),
                MaterialRequest.sap_material_code.ilike(like),
            )
        )
    stmt = stmt.order_by(MaterialRequest.updated_at.desc(), MaterialRequest.id.desc()).limit(limit)
    return list(session.scalars(stmt))


# ---------------------------------------------------------------- histórico

def _history(
    session: Session,
    req: MaterialRequest,
    actor: CurrentUser,
    *,
    event: HistoryEvent,
    from_status: RequestStatus | None,
    to_status: RequestStatus,
    note: str | None = None,
    changes: Mapping[str, Any] | None = None,
) -> None:
    # Gravado pela relação (e não só por request_id) para `req.history` ficar sempre atualizado.
    req.history.append(
        RequestHistory(
            user_id=actor.id,
            occurred_at=clock.now(),
            event_type=event,
            from_status=from_status,
            to_status=to_status,
            note=note,
            changes=jsonable(dict(changes)) if changes else None,
        )
    )


def _touch(req: MaterialRequest) -> None:
    req.updated_at = clock.now()


def _diff(req: MaterialRequest, new_values: Mapping[str, Any]) -> dict[str, list[Any]]:
    changes: dict[str, list[Any]] = {}
    for field, new in new_values.items():
        old = getattr(req, field)
        if old != new:
            changes[field] = [old, new]
            setattr(req, field, new)
    return changes


def _for_edit(session: Session, actor: CurrentUser, request_id: int, *, kind: str) -> MaterialRequest:
    req = get_request(session, actor, request_id, for_update=True)
    if kind == "technical":
        allowed = access.can_edit_technical(actor, status=req.status, created_by_id=req.created_by_id)
        message = "Só o autor pode editar os dados técnicos, e apenas em rascunho ou depois de devolvida."
    elif kind == "commercial":
        allowed = access.can_edit_commercial(actor, status=req.status)
        message = "A informação comercial só pode ser editada por Compras enquanto a solicitação está pendente em Compras."
    else:
        allowed = access.can_edit_sap_fields(actor, status=req.status)
        message = "Os campos SAP só podem ser editados por Dados Mestre enquanto a solicitação está pendente em Dados Mestre."
    if not allowed:
        raise PermissionDenied(message)
    return req


# ---------------------------------------------------------------- normalização de valores

def _normalize_technical(raw: Mapping[str, Any], session: Session) -> dict[str, Any]:
    unknown = set(raw) - TECHNICAL_FIELDS
    if unknown:
        raise ValidationError(f"Campos desconhecidos: {', '.join(sorted(unknown))}.")
    errors: list[str] = []
    values: dict[str, Any] = {}
    for field, value in raw.items():
        try:
            if field in _TEXT_FIELDS:
                label, size = _TEXT_FIELDS[field]
                values[field] = clean_text(value, label=label, max_length=size, required=field == "original_description")
            elif field in _DECIMAL_FIELDS:
                number = parse_decimal(value if isinstance(value, str) else (None if value is None else str(value)), field=_DECIMAL_FIELDS[field])
                if number is not None and number < 0:
                    raise ValidationError(f"O campo «{_DECIMAL_FIELDS[field]}» não pode ser negativo.")
                values[field] = number
            elif field in ("description_pt", "description_en"):
                if value is None or str(value).strip() == "":
                    values[field] = None
                else:
                    check = check_descriptor(str(value))
                    if not check.ok:
                        which = "PT-PT" if field == "description_pt" else "EN"
                        raise ValidationError(f"Descritivo {which}: {'; '.join(check.errors)}.")
                    values[field] = check.normalized
            elif field == "category_id":
                if value in (None, ""):
                    values[field] = None
                else:
                    category = session.get(ComponentCategory, int(value))
                    if category is None or not category.is_active:
                        raise ValidationError("A categoria escolhida não existe.")
                    values[field] = category.id
        except ValueError as exc:
            errors.append(str(exc))
        except ValidationError as exc:
            errors.extend(exc.errors)
    if errors:
        raise ValidationError(errors)
    if "net_weight" in values and "gross_weight" in values:
        net, gross = values["net_weight"], values["gross_weight"]
        if net is not None and gross is not None and gross < net:
            raise ValidationError("O peso bruto não pode ser inferior ao peso líquido.")
    return values


# ---------------------------------------------------------------- criação e edição técnica

def create_request(session: Session, actor: CurrentUser, data: Mapping[str, Any]) -> MaterialRequest:
    require_permission(actor, Permission.REQUEST_CREATE)
    if not (data.get("original_description") or "").strip():
        raise ValidationError("A descrição original é obrigatória.")
    values = _normalize_technical(data, session)
    now = clock.now()
    req = MaterialRequest(
        status=RequestStatus.RASCUNHO, created_by_id=actor.id, created_at=now, updated_at=now, **values
    )
    session.add(req)
    session.flush()
    req.internal_code = f"SOL-{now.year}-{req.id:06d}"
    _history(session, req, actor, event=HistoryEvent.CRIACAO, from_status=None, to_status=RequestStatus.RASCUNHO)
    audit.record(session, "SOLICITACAO_CRIADA", actor=actor, entity_type="material_request", entity_id=req.id)
    session.flush()
    return get_request(session, actor, req.id)


def update_technical(session: Session, actor: CurrentUser, request_id: int, data: Mapping[str, Any]) -> MaterialRequest:
    req = _for_edit(session, actor, request_id, kind="technical")
    values = _normalize_technical(data, session)
    if "original_description" in values and not values["original_description"]:
        raise ValidationError("A descrição original é obrigatória.")
    if ("net_weight" in values) != ("gross_weight" in values):
        net = values.get("net_weight", req.net_weight)
        gross = values.get("gross_weight", req.gross_weight)
        if net is not None and gross is not None and gross < net:
            raise ValidationError("O peso bruto não pode ser inferior ao peso líquido.")
    changes = _diff(req, values)
    if changes:
        _touch(req)
        _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status, changes=changes)
        audit.record(
            session, "SOLICITACAO_ALTERADA", actor=actor, entity_type="material_request", entity_id=req.id,
            details={"campos": sorted(changes)},
        )
    session.flush()
    return req


def apply_category_template(session: Session, actor: CurrentUser, request_id: int) -> int:
    """Acrescenta os campos sugeridos da categoria que ainda não existem (valores vazios)."""
    req = _for_edit(session, actor, request_id, kind="technical")
    if req.category is None:
        raise ValidationError("Escolha primeiro a categoria do componente.")
    present = {c.label.casefold() for c in req.characteristics}
    order = max((c.sort_order for c in req.characteristics), default=-1) + 1
    added: list[str] = []
    for field in req.category.fields:
        if field.label.casefold() not in present:
            req.characteristics.append(MaterialCharacteristic(label=field.label, sort_order=order))
            order += 1
            added.append(field.label)
    if added:
        _touch(req)
        _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status,
                 changes={"campos_sugeridos_adicionados": added})
    session.flush()
    return len(added)


def set_characteristics(
    session: Session, actor: CurrentUser, request_id: int, rows: list[Mapping[str, Any]]
) -> MaterialRequest:
    """Substitui as características técnicas.

    Valor vazio significa «não identificado» (nunca se inventa). Um valor preenchido exige origem.
    """
    req = _for_edit(session, actor, request_id, kind="technical")
    cleaned: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        label = " ".join(str(row.get("label") or "").split())
        value = " ".join(str(row.get("value") or "").split()) or None
        unit = " ".join(str(row.get("unit") or "").split()) or None
        source = row.get("source")
        if not label and not value and not unit:
            continue
        if not label:
            errors.append(f"Linha {index}: indique o nome da característica.")
            continue
        if len(label) > 100 or (value and len(value) > 255) or (unit and len(unit) > 20):
            errors.append(f"Linha {index}: texto demasiado longo.")
            continue
        if label.casefold() in seen:
            errors.append(f"A característica «{label}» está repetida.")
            continue
        seen.add(label.casefold())
        if value:
            try:
                source = CharacteristicSource(source)
            except ValueError:
                errors.append(f"«{label}»: indique a origem do valor.")
                continue
        else:
            source, unit = None, None
        cleaned.append({"label": label, "value": value, "unit": unit, "source": source})
    if errors:
        raise ValidationError(errors)

    before = [(c.label, c.value, c.unit, c.source) for c in req.characteristics]
    after = [(c["label"], c["value"], c["unit"], c["source"]) for c in cleaned]
    if before != after:
        req.characteristics.clear()
        session.flush()
        for order, item in enumerate(cleaned):
            req.characteristics.append(MaterialCharacteristic(sort_order=order, **item))
        _touch(req)
        _history(
            session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status,
            changes={"caracteristicas": {"antes": [list(b) for b in before], "depois": [list(a) for a in after]}},
        )
        audit.record(session, "CARACTERISTICAS_ALTERADAS", actor=actor, entity_type="material_request", entity_id=req.id)
    session.flush()
    return req


# ---------------------------------------------------------------- anexos

def add_attachment(
    session: Session, actor: CurrentUser, request_id: int, kind: AttachmentKind, filename: str, data: bytes
) -> Attachment:
    req = _for_edit(session, actor, request_id, kind="technical")
    settings = get_settings()
    if len(req.attachments) >= settings.max_attachments_per_request:
        raise ValidationError(f"Cada solicitação aceita no máximo {settings.max_attachments_per_request} ficheiros.")
    checked = validate_upload(
        filename, data, kind, max_image_bytes=settings.max_image_bytes, max_pdf_bytes=settings.max_pdf_bytes
    )
    if any(a.sha256 == checked.sha256 for a in req.attachments):
        raise ConflictError("Este ficheiro já foi carregado nesta solicitação.")
    key = storage.new_key()
    storage.save(key, data)
    attachment = Attachment(
        kind=kind,
        original_filename=checked.safe_filename,
        content_type=checked.content_type,
        size_bytes=checked.size_bytes,
        sha256=checked.sha256,
        storage_key=key,
        uploaded_by_id=actor.id,
        uploaded_at=clock.now(),
    )
    req.attachments.append(attachment)
    _touch(req)
    _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status,
             changes={"anexo_adicionado": checked.safe_filename})
    audit.record(session, "ANEXO_ADICIONADO", actor=actor, entity_type="material_request", entity_id=req.id,
                 details={"tipo": kind, "ficheiro": checked.safe_filename})
    session.flush()
    return attachment


def remove_attachment(session: Session, actor: CurrentUser, request_id: int, attachment_id: int) -> None:
    req = _for_edit(session, actor, request_id, kind="technical")
    attachment = next((a for a in req.attachments if a.id == attachment_id), None)
    if attachment is None:
        raise NotFoundError("Ficheiro não encontrado.")
    key, name = attachment.storage_key, attachment.original_filename
    req.attachments.remove(attachment)
    _touch(req)
    _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status,
             changes={"anexo_removido": name})
    audit.record(session, "ANEXO_REMOVIDO", actor=actor, entity_type="material_request", entity_id=req.id,
                 details={"ficheiro": name})
    session.flush()
    storage.delete(key)


def read_attachment(session: Session, actor: CurrentUser, request_id: int, attachment_id: int) -> tuple[Attachment, bytes]:
    req = get_request(session, actor, request_id)
    attachment = next((a for a in req.attachments if a.id == attachment_id), None)
    if attachment is None:
        raise NotFoundError("Ficheiro não encontrado.")
    return attachment, storage.read(attachment.storage_key)


# ---------------------------------------------------------------- informação comercial (Compras)

def _offer_values(data: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    values: dict[str, Any] = {}
    try:
        values["supplier_name"] = clean_text(data.get("supplier_name"), label="Fornecedor", max_length=150, required=True)
        values["supplier_reference"] = clean_text(data.get("supplier_reference"), label="Referência do fornecedor", max_length=100)
        values["purchase_unit"] = clean_text(data.get("purchase_unit"), label="Unidade de compra", max_length=10)
        values["price_reference"] = clean_text(data.get("price_reference"), label="Referência do preço", max_length=100)
        values["notes"] = clean_text(data.get("notes"), label="Notas", max_length=255)
    except ValidationError as exc:
        errors += exc.errors
    for field, label in (("purchase_price", "Preço de compra"), ("quantity_per_package", "Quantidade por embalagem")):
        try:
            raw = data.get(field)
            number = parse_decimal(raw if isinstance(raw, str) or raw is None else str(raw), field=label)
            if number is not None and number < 0:
                errors.append(f"O campo «{label}» não pode ser negativo.")
            if field == "quantity_per_package" and number is not None and number == 0:
                errors.append("A quantidade por embalagem tem de ser superior a zero.")
            values[field] = number
        except ValueError as exc:
            errors.append(str(exc))
    currency = (data.get("currency") or "").strip().upper()
    if currency and not (len(currency) == 3 and currency.isalpha()):
        errors.append("A moeda deve ter o código de 3 letras (por exemplo EUR).")
    values["currency"] = currency or None
    if values.get("purchase_price") is not None and not values["currency"]:
        errors.append("Indique a moeda do preço.")
    values["price_valid_until"] = data.get("price_valid_until") or None
    if errors:
        raise ValidationError(errors)
    return values


def add_offer(session: Session, actor: CurrentUser, request_id: int, data: Mapping[str, Any]) -> SupplierOffer:
    req = _for_edit(session, actor, request_id, kind="commercial")
    offer = SupplierOffer(created_by_id=actor.id, created_at=clock.now(), updated_at=clock.now(), **_offer_values(data))
    req.offers.append(offer)
    _touch(req)
    _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status,
             changes={"fornecedor_adicionado": offer.supplier_name})
    audit.record(session, "FORNECEDOR_ADICIONADO", actor=actor, entity_type="material_request", entity_id=req.id)
    session.flush()
    return offer


def update_offer(session: Session, actor: CurrentUser, request_id: int, offer_id: int, data: Mapping[str, Any]) -> SupplierOffer:
    req = _for_edit(session, actor, request_id, kind="commercial")
    offer = next((o for o in req.offers if o.id == offer_id), None)
    if offer is None:
        raise NotFoundError("Fornecedor não encontrado.")
    values = _offer_values(data)
    changes: dict[str, list[Any]] = {}
    for field, new in values.items():
        if getattr(offer, field) != new:
            changes[field] = [getattr(offer, field), new]
            setattr(offer, field, new)
    if changes:
        offer.updated_at = clock.now()
        _touch(req)
        _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status,
                 changes={f"fornecedor_{offer.id}": changes})
    session.flush()
    return offer


def remove_offer(session: Session, actor: CurrentUser, request_id: int, offer_id: int) -> None:
    req = _for_edit(session, actor, request_id, kind="commercial")
    offer = next((o for o in req.offers if o.id == offer_id), None)
    if offer is None:
        raise NotFoundError("Fornecedor não encontrado.")
    name = offer.supplier_name
    req.offers.remove(offer)
    _touch(req)
    _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status,
             changes={"fornecedor_removido": name})
    session.flush()


# ---------------------------------------------------------------- campos SAP (Dados Mestre)

def update_sap_fields(session: Session, actor: CurrentUser, request_id: int, data: Mapping[str, Any]) -> MaterialRequest:
    """Não aceita o código SAP: esse só se regista ao concluir, e nunca é gerado automaticamente."""
    req = _for_edit(session, actor, request_id, kind="sap")
    unknown = set(data) - set(SAP_FIELDS)
    if unknown:
        raise ValidationError(f"Campos desconhecidos: {', '.join(sorted(unknown))}.")
    values = {
        field: clean_text(value, label=SAP_FIELDS[field][0], max_length=SAP_FIELDS[field][1])
        for field, value in data.items()
    }
    changes = _diff(req, values)
    if changes:
        _touch(req)
        _history(session, req, actor, event=HistoryEvent.ALTERACAO, from_status=req.status, to_status=req.status, changes=changes)
        audit.record(session, "CAMPOS_SAP_ALTERADOS", actor=actor, entity_type="material_request", entity_id=req.id)
    session.flush()
    return req


# ---------------------------------------------------------------- workflow

def validation_problems(req: MaterialRequest, target: RequestStatus) -> list[str]:
    """Campos obrigatórios para entrar no estado de destino."""
    problems: list[str] = []
    if target == RequestStatus.PENDENTE_COMPRAS:
        if not (req.original_description or "").strip():
            problems.append("Falta a descrição original.")
        if req.category_id is None:
            problems.append("Falta a categoria do componente.")
        for label, text in (("PT-PT", req.description_pt), ("EN", req.description_en)):
            check = check_descriptor(text)
            if not check.ok:
                problems.append(f"Descritivo {label}: {'; '.join(check.errors)}.")
    elif target == RequestStatus.PENDENTE_DADOS_MESTRE:
        complete = [
            o for o in req.offers if o.supplier_name and o.purchase_price is not None and o.currency and o.purchase_unit
        ]
        if not complete:
            problems.append("Registe pelo menos um fornecedor com preço, moeda e unidade de compra.")
    elif target == RequestStatus.APROVADO_PARA_SAP:
        for field, label in REQUIRED_SAP_FIELDS.items():
            if not getattr(req, field):
                problems.append(f"Falta preencher: {label}.")
        for label, text in (("PT-PT", req.description_pt), ("EN", req.description_en)):
            check = check_descriptor(text)
            if not check.ok:
                problems.append(f"Descritivo {label}: {'; '.join(check.errors)}.")
    return problems


def transition(
    session: Session,
    actor: CurrentUser,
    request_id: int,
    target: RequestStatus,
    *,
    note: str | None = None,
    sap_code: str | None = None,
) -> MaterialRequest:
    req = get_request(session, actor, request_id, for_update=True)
    step = find_transition(req.status, target)
    if step is None:
        raise ConflictError("Esta mudança de estado não é permitida a partir do estado atual.")
    require_permission(actor, step.permission, "O seu departamento não pode executar esta mudança de estado.")
    if step.owner_only and req.created_by_id != actor.id:
        raise PermissionDenied("Só o autor da solicitação a pode submeter.")
    observation = clean_text(note, label="Observações", max_length=2000)
    if step.requires_note and not observation:
        raise ValidationError("Indique nas observações o que tem de ser corrigido.")

    problems = validation_problems(req, target)
    code = None
    if target == RequestStatus.CONCLUIDO_NO_SAP:
        code = clean_text(sap_code, label="Código de material SAP", max_length=40, required=True)
        clash = session.scalar(
            select(MaterialRequest.id).where(MaterialRequest.sap_material_code == code, MaterialRequest.id != req.id)
        )
        if clash:
            problems.append("Este código SAP já está registado noutra solicitação.")
    if problems:
        raise ValidationError(problems)

    previous = req.status
    req.status = target
    now = clock.now()
    req.updated_at = now
    if target == RequestStatus.PENDENTE_COMPRAS:
        req.submitted_at = now
    changes: dict[str, Any] | None = None
    if code:
        req.sap_material_code = code
        changes = {"sap_material_code": [None, code]}
    _history(session, req, actor, event=HistoryEvent.TRANSICAO, from_status=previous, to_status=target,
             note=observation, changes=changes)
    audit.record(
        session, "ESTADO_ALTERADO", actor=actor, entity_type="material_request", entity_id=req.id,
        details={"de": previous, "para": target},
    )
    session.flush()
    return req


def available_transitions(actor: CurrentUser, req: MaterialRequest):
    from app.domain.permissions import has_permission
    from app.domain.workflow import transitions_from

    return [
        t for t in transitions_from(req.status)
        if has_permission(actor, t.permission) and (not t.owner_only or req.created_by_id == actor.id)
    ]


__all__ = [
    "REQUIRED_SAP_FIELDS", "add_attachment", "add_offer", "apply_category_template",
    "available_transitions", "create_request", "get_request", "list_requests", "read_attachment",
    "remove_attachment", "remove_offer", "set_characteristics", "transition", "update_offer",
    "update_sap_fields", "update_technical", "validation_problems",
]
