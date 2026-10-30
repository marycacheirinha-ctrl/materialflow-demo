import io
from decimal import Decimal

import pytest
from PIL import Image
from sqlalchemy import select

from app.db import session as db_session
from app.db.models import ComponentCategory
from app.domain.enums import AttachmentKind, CharacteristicSource
from app.domain.errors import ConflictError, NotFoundError, PermissionDenied, ValidationError
from app.services import requests, storage


def _cat(session, code="RESISTENCIA"):
    return session.scalar(select(ComponentCategory).where(ComponentCategory.code == code))


def _new(session, tec, **extra):
    return requests.create_request(session, tec, {"original_description": "Resistência da caldeira", **extra})


def _png(color="white") -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), color).save(buf, "PNG")
    return buf.getvalue()


PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def test_criar_solicitacao_gera_rascunho_e_codigo_interno(session, tec):
    req = _new(session, tec)
    assert req.status.value == "RASCUNHO"
    assert req.internal_code.startswith("SOL-")
    assert req.sap_material_code is None  # nunca é gerado automaticamente
    assert [h.event_type.value for h in req.history] == ["CRIACAO"]


def test_so_tecnicos_criam(session, compras, dm):
    for actor in (compras, dm):
        with pytest.raises(PermissionDenied):
            requests.create_request(session, actor, {"original_description": "x"})


def test_descricao_original_obrigatoria(session, tec):
    with pytest.raises(ValidationError):
        requests.create_request(session, tec, {"original_description": "   "})


def test_descritivo_acima_de_40_caracteres_e_rejeitado_e_nunca_cortado(session, tec):
    req = _new(session, tec)
    longo = "RESISTÊNCIA DE AQUECIMENTO EM INOX 2400W 230V"
    with pytest.raises(ValidationError) as exc:
        requests.update_technical(session, tec, req.id, {"description_pt": longo})
    assert "máximo é 40" in str(exc.value)
    assert req.description_pt is None  # nada foi gravado, nem cortado


def test_descritivos_sao_normalizados_ao_gravar(session, tec):
    req = _new(session, tec)
    requests.update_technical(
        session, tec, req.id, {"description_pt": " resistência 2400w 230v. ", "description_en": "heating element 2400W 230V"}
    )
    assert req.description_pt == "RESISTÊNCIA 2400W 230V"
    assert req.description_en == "HEATING ELEMENT 2400W 230V"


def test_alteracoes_ficam_no_historico_com_antes_e_depois(session, tec):
    req = _new(session, tec)
    requests.update_technical(session, tec, req.id, {"brand": "ACME"})
    last = req.history[-1]
    assert last.event_type.value == "ALTERACAO" and last.changes == {"brand": [None, "ACME"]}


def test_so_o_autor_edita_o_rascunho(session, tec, tec2):
    req = _new(session, tec)
    with pytest.raises(NotFoundError):  # rascunhos alheios nem são visíveis
        requests.update_technical(session, tec2, req.id, {"brand": "X"})


def test_rascunho_invisivel_para_compras_e_dados_mestre(session, tec, compras, dm):
    req = _new(session, tec)
    for actor in (compras, dm):
        with pytest.raises(NotFoundError):
            requests.get_request(session, actor, req.id)
        assert requests.list_requests(session, actor) == []
    assert [r.id for r in requests.list_requests(session, tec)] == [req.id]


def test_caracteristicas_valor_exige_origem_e_vazio_e_nao_identificado(session, tec):
    req = _new(session, tec, category_id=_cat(session).id)
    with pytest.raises(ValidationError):
        requests.set_characteristics(session, tec, req.id, [{"label": "Potência", "value": "2400", "unit": "W", "source": None}])
    requests.set_characteristics(
        session, tec, req.id,
        [
            {"label": "Potência", "value": "2400", "unit": "W", "source": CharacteristicSource.FICHA_TECNICA},
            {"label": "Material", "value": "", "unit": "mm", "source": CharacteristicSource.FOTOGRAFIA},
        ],
    )
    power, material = req.characteristics
    assert power.source == CharacteristicSource.FICHA_TECNICA
    assert material.value is None and material.source is None and material.unit is None  # não identificado


def test_caracteristicas_repetidas_sao_rejeitadas(session, tec):
    req = _new(session, tec)
    rows = [{"label": "Tensão", "value": "230", "source": "INTRODUCAO_MANUAL"}] * 2
    with pytest.raises(ValidationError):
        requests.set_characteristics(session, tec, req.id, rows)


def test_campos_sugeridos_da_categoria_sem_valores_nem_duplicados(session, tec):
    req = _new(session, tec, category_id=_cat(session, "ELETROVALVULA").id)
    assert requests.apply_category_template(session, tec, req.id) == 5
    assert all(c.value is None for c in req.characteristics)
    assert "Número de vias" in [c.label for c in req.characteristics]
    assert requests.apply_category_template(session, tec, req.id) == 0  # idempotente


def test_anexos_validos_duplicados_e_invalidos(session, tec):
    req = _new(session, tec)
    foto = requests.add_attachment(session, tec, req.id, AttachmentKind.FOTOGRAFIA, "peca.png", _png())
    requests.add_attachment(session, tec, req.id, AttachmentKind.FICHA_TECNICA, "ficha.pdf", PDF)
    assert storage.read(foto.storage_key) == _png()
    with pytest.raises(ConflictError):
        requests.add_attachment(session, tec, req.id, AttachmentKind.FOTOGRAFIA, "outra.png", _png())
    with pytest.raises(ValidationError):
        requests.add_attachment(session, tec, req.id, AttachmentKind.FOTOGRAFIA, "virus.png", b"MZ\x90\x00")
    with pytest.raises(ValidationError):
        requests.add_attachment(session, tec, req.id, AttachmentKind.FICHA_TECNICA, "ficha.pdf", _png("red"))


def test_remover_anexo_apaga_o_ficheiro(session, tec):
    req = _new(session, tec)
    foto = requests.add_attachment(session, tec, req.id, AttachmentKind.FOTOGRAFIA, "peca.png", _png())
    key = foto.storage_key
    requests.remove_attachment(session, tec, req.id, foto.id)
    with pytest.raises(FileNotFoundError):
        storage.read(key)


def test_logistica_decimais_e_regra_do_peso(session, tec):
    req = _new(session, tec)
    requests.update_technical(session, tec, req.id, {"net_weight": "1,250", "gross_weight": "1.400,5", "length": "12,5"})
    assert req.net_weight == Decimal("1.250") and req.gross_weight == Decimal("1400.5")
    with pytest.raises(ValidationError):
        requests.update_technical(session, tec, req.id, {"gross_weight": "1"})  # bruto < líquido
    with pytest.raises(ValidationError):
        requests.update_technical(session, tec, req.id, {"net_weight": "-2"})
    with pytest.raises(ValidationError):
        requests.update_technical(session, tec, req.id, {"width": "abc"})


def test_persistencia_numa_sessao_nova(session, tec):
    req = _new(session, tec, brand="ACME", category_id=_cat(session).id)
    requests.update_technical(session, tec, req.id, {"description_pt": "RESISTÊNCIA 2400W 230V", "net_weight": "0,35"})
    requests.set_characteristics(session, tec, req.id, [{"label": "Tensão", "value": "230", "unit": "V", "source": "FOTOGRAFIA"}])
    session.commit()
    with db_session.session_scope() as other:
        saved = requests.get_request(other, tec, req.id)
        assert saved.brand == "ACME" and saved.description_pt == "RESISTÊNCIA 2400W 230V"
        assert saved.net_weight == Decimal("0.35")
        assert saved.characteristics[0].value == "230" and saved.category.code == "RESISTENCIA"
