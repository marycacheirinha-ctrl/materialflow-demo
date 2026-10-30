import pytest

from app.domain.descriptors import MAX_DESCRIPTOR_LENGTH, check_descriptor, normalize_descriptor


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("caixa de borras", "CAIXA DE BORRAS"),
        ("  eletroválvula   2 vias. ", "ELETROVÁLVULA 2 VIAS"),
        ("Sensor NTC universal...", "SENSOR NTC UNIVERSAL"),
        (None, ""),
        ("", ""),
    ],
)
def test_normaliza_maiusculas_espacos_e_ponto_final(raw, expected):
    assert normalize_descriptor(raw) == expected


def test_exemplos_do_enunciado_sao_validos():
    for text in [
        "CAIXA DE BORRAS",
        "COFFEE GROUNDS BOX",
        "ELETROVÁLVULA 2 VIAS",
        "2-WAY SOLENOID VALVE",
        "SENSOR NTC UNIVERSAL",
        "UNIVERSAL NTC SENSOR",
        "RESISTÊNCIA 2400W 230V",
        "HEATING ELEMENT 2400W 230V",
    ]:
        assert check_descriptor(text).ok, text


def test_limite_de_40_caracteres_inclui_espacos():
    exato = "A" * MAX_DESCRIPTOR_LENGTH
    assert check_descriptor(exato).ok
    assert check_descriptor(exato).length == 40
    excedido = check_descriptor("A" * 41)
    assert not excedido.ok
    assert "41" in excedido.errors[0]


def test_nunca_corta_o_texto_automaticamente():
    longo = "RESISTÊNCIA AQUECIMENTO INOX 2400W 230V COM FLANGE"
    resultado = check_descriptor(longo)
    assert not resultado.ok
    assert resultado.normalized == longo  # intacto, só normalizado


def test_vazio_e_invalido():
    assert not check_descriptor("   ").ok
    assert not check_descriptor(None).ok


def test_caracteres_de_controlo_sao_rejeitados():
    assert not check_descriptor("VALVULA\x00").ok
