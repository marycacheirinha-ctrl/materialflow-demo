from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import ComponentCategory
from app.domain.enums import RequestStatus as S
from app.domain.errors import ConflictError, NotFoundError, PermissionDenied, ValidationError
from app.services import requests

OFFER = {"supplier_name": "Fornecedor Exemplo", "purchase_price": "12,50", "currency": "eur", "purchase_unit": "UN"}
SAP = {
    "sap_material_type": "ERSA",
    "sap_material_group": "ELE001",
    "base_unit": "UN",
    "sap_plant": "1000",
    "sap_purchasing_org": "PT01",
}


def _ready_draft(session, tec, pt="RESISTÊNCIA 2400W 230V", en="HEATING ELEMENT 2400W 230V"):
    cat = session.scalar(select(ComponentCategory).where(ComponentCategory.code == "RESISTENCIA"))
    return requests.create_request(
        session, tec,
        {"original_description": "Resistência da caldeira", "category_id": cat.id, "description_pt": pt, "description_en": en},
    )


def _to_dm(session, tec, compras, **kw):
    req = _ready_draft(session, tec, **kw)
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    requests.add_offer(session, compras, req.id, OFFER)
    requests.transition(session, compras, req.id, S.PENDENTE_DADOS_MESTRE)
    return req


def test_fluxo_completo_tecnicos_compras_dados_mestre(session, tec, compras, dm):
    req = _ready_draft(session, tec)
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    assert req.status == S.PENDENTE_COMPRAS and req.submitted_at is not None

    requests.add_offer(session, compras, req.id, OFFER)
    requests.transition(session, compras, req.id, S.PENDENTE_DADOS_MESTRE)

    requests.update_sap_fields(session, dm, req.id, SAP)
    requests.transition(session, dm, req.id, S.APROVADO_PARA_SAP)
    assert req.sap_material_code is None  # aprovar não gera código

    requests.transition(session, dm, req.id, S.CONCLUIDO_NO_SAP, sap_code="1000234567")
    assert req.status == S.CONCLUIDO_NO_SAP and req.sap_material_code == "1000234567"

    transitions = [h for h in req.history if h.event_type.value == "TRANSICAO"]
    assert [(h.from_status, h.to_status) for h in transitions] == [
        (S.RASCUNHO, S.PENDENTE_COMPRAS),
        (S.PENDENTE_COMPRAS, S.PENDENTE_DADOS_MESTRE),
        (S.PENDENTE_DADOS_MESTRE, S.APROVADO_PARA_SAP),
        (S.APROVADO_PARA_SAP, S.CONCLUIDO_NO_SAP),
    ]
    assert [h.user.username for h in transitions] == ["tecnico", "compras", "dadosmestre", "dadosmestre"]
    assert all(h.occurred_at is not None for h in transitions)


def test_so_dados_mestre_aprova_e_conclui(session, tec, compras, dm):
    req = _to_dm(session, tec, compras)
    requests.update_sap_fields(session, dm, req.id, SAP)
    for actor in (tec, compras):
        with pytest.raises(PermissionDenied):
            requests.transition(session, actor, req.id, S.APROVADO_PARA_SAP)
    requests.transition(session, dm, req.id, S.APROVADO_PARA_SAP)
    for actor in (tec, compras):
        with pytest.raises(PermissionDenied):
            requests.transition(session, actor, req.id, S.CONCLUIDO_NO_SAP, sap_code="1")


def test_nao_ha_saltos_de_estado(session, tec, compras, dm):
    req = _ready_draft(session, tec)
    with pytest.raises(ConflictError):
        requests.transition(session, tec, req.id, S.PENDENTE_DADOS_MESTRE)
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    with pytest.raises(ConflictError):
        requests.transition(session, compras, req.id, S.APROVADO_PARA_SAP)


def test_submeter_exige_categoria_e_descritivos_validos(session, tec):
    req = requests.create_request(session, tec, {"original_description": "peça"})
    with pytest.raises(ValidationError) as exc:
        requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    message = str(exc.value)
    assert "categoria" in message and "PT-PT" in message and "EN" in message
    assert req.status == S.RASCUNHO


def test_so_o_autor_submete(session, tec, tec2):
    req = _ready_draft(session, tec)
    with pytest.raises(NotFoundError):
        requests.transition(session, tec2, req.id, S.PENDENTE_COMPRAS)


def test_encaminhar_exige_fornecedor_completo(session, tec, compras):
    req = _ready_draft(session, tec)
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    with pytest.raises(ValidationError):
        requests.transition(session, compras, req.id, S.PENDENTE_DADOS_MESTRE)
    requests.add_offer(session, compras, req.id, {"supplier_name": "Sem preço"})
    with pytest.raises(ValidationError):  # fornecedor sem preço, moeda e unidade
        requests.transition(session, compras, req.id, S.PENDENTE_DADOS_MESTRE)


def test_aprovar_exige_campos_sap_e_descritivos(session, tec, compras, dm):
    req = _to_dm(session, tec, compras)
    with pytest.raises(ValidationError) as exc:
        requests.transition(session, dm, req.id, S.APROVADO_PARA_SAP)
    assert "Tipo de material" in str(exc.value) and "Centro" in str(exc.value)
    assert req.status == S.PENDENTE_DADOS_MESTRE


def test_devolver_exige_observacoes_e_volta_ao_autor(session, tec, compras):
    req = _ready_draft(session, tec)
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    with pytest.raises(ValidationError):
        requests.transition(session, compras, req.id, S.DEVOLVIDO_PARA_CORRECAO)
    requests.transition(session, compras, req.id, S.DEVOLVIDO_PARA_CORRECAO, note="Falta a tensão nominal")
    assert req.status == S.DEVOLVIDO_PARA_CORRECAO and req.history[-1].note == "Falta a tensão nominal"

    requests.update_technical(session, tec, req.id, {"brand": "ACME"})  # o autor corrige
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    assert req.status == S.PENDENTE_COMPRAS


def test_dados_mestre_tambem_devolve(session, tec, compras, dm):
    req = _to_dm(session, tec, compras)
    requests.transition(session, dm, req.id, S.DEVOLVIDO_PARA_CORRECAO, note="Descritivo ambíguo")
    assert req.status == S.DEVOLVIDO_PARA_CORRECAO


def test_edicao_bloqueada_fora_do_estado_e_do_departamento(session, tec, compras, dm):
    req = _ready_draft(session, tec)
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    with pytest.raises(PermissionDenied):  # autor já não edita depois de submeter
        requests.update_technical(session, tec, req.id, {"brand": "X"})
    with pytest.raises(PermissionDenied):  # Compras não edita dados técnicos
        requests.update_technical(session, compras, req.id, {"brand": "X"})
    with pytest.raises(PermissionDenied):  # Dados Mestre não edita informação comercial
        requests.add_offer(session, dm, req.id, OFFER)
    requests.add_offer(session, compras, req.id, OFFER)
    requests.transition(session, compras, req.id, S.PENDENTE_DADOS_MESTRE)
    with pytest.raises(PermissionDenied):  # fora de PENDENTE COMPRAS, Compras já não edita
        requests.add_offer(session, compras, req.id, OFFER)
    with pytest.raises(PermissionDenied):
        requests.update_sap_fields(session, compras, req.id, SAP)


def test_codigo_sap_nao_se_define_fora_da_conclusao(session, tec, compras, dm):
    req = _to_dm(session, tec, compras)
    with pytest.raises(ValidationError):
        requests.update_sap_fields(session, dm, req.id, {"sap_material_code": "999"})
    requests.update_sap_fields(session, dm, req.id, SAP)
    requests.transition(session, dm, req.id, S.APROVADO_PARA_SAP)
    with pytest.raises(ValidationError):  # concluir sem código
        requests.transition(session, dm, req.id, S.CONCLUIDO_NO_SAP)
    assert req.sap_material_code is None


def test_codigo_sap_nao_pode_repetir(session, tec, compras, dm):
    codes = []
    for _ in range(2):
        req = _to_dm(session, tec, compras)
        requests.update_sap_fields(session, dm, req.id, SAP)
        requests.transition(session, dm, req.id, S.APROVADO_PARA_SAP)
        codes.append(req)
    requests.transition(session, dm, codes[0].id, S.CONCLUIDO_NO_SAP, sap_code="5000001")
    with pytest.raises(ValidationError) as exc:
        requests.transition(session, dm, codes[1].id, S.CONCLUIDO_NO_SAP, sap_code="5000001")
    assert "já está registado" in str(exc.value)


def test_concluido_e_final(session, tec, compras, dm):
    req = _to_dm(session, tec, compras)
    requests.update_sap_fields(session, dm, req.id, SAP)
    requests.transition(session, dm, req.id, S.APROVADO_PARA_SAP)
    requests.transition(session, dm, req.id, S.CONCLUIDO_NO_SAP, sap_code="7000001")
    for target in S:
        with pytest.raises(ConflictError):
            requests.transition(session, dm, req.id, target)
    assert requests.available_transitions(dm, req) == []


def test_oferta_validacoes_e_varios_fornecedores(session, tec, compras):
    req = _ready_draft(session, tec)
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    with pytest.raises(ValidationError):
        requests.add_offer(session, compras, req.id, {"supplier_name": ""})
    with pytest.raises(ValidationError):
        requests.add_offer(session, compras, req.id, {"supplier_name": "A", "purchase_price": "5"})  # sem moeda
    with pytest.raises(ValidationError):
        requests.add_offer(session, compras, req.id, {"supplier_name": "A", "purchase_price": "-1", "currency": "EUR"})
    with pytest.raises(ValidationError):
        requests.add_offer(session, compras, req.id, {"supplier_name": "A", "currency": "EURO"})
    first = requests.add_offer(session, compras, req.id, OFFER)
    requests.add_offer(session, compras, req.id, {**OFFER, "supplier_name": "Outro Fornecedor", "purchase_price": "11,90"})
    assert len(req.offers) == 2 and first.currency == "EUR"
    assert {o.purchase_price for o in req.offers} == {Decimal("12.50"), Decimal("11.90")}


def test_acoes_disponiveis_por_departamento(session, tec, compras, dm):
    req = _ready_draft(session, tec)
    assert [t.target for t in requests.available_transitions(tec, req)] == [S.PENDENTE_COMPRAS]
    assert requests.available_transitions(compras, req) == []
    requests.transition(session, tec, req.id, S.PENDENTE_COMPRAS)
    assert requests.available_transitions(tec, req) == []
    assert {t.target for t in requests.available_transitions(compras, req)} == {S.PENDENTE_DADOS_MESTRE, S.DEVOLVIDO_PARA_CORRECAO}
    assert requests.available_transitions(dm, req) == []
