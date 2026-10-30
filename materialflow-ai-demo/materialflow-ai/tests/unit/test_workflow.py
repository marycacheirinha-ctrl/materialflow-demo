import itertools

from app.domain.enums import RequestStatus as S
from app.domain.permissions import Permission
from app.domain.workflow import TRANSITIONS, find_transition, transitions_from


def test_sequencia_obrigatoria_tecnicos_compras_dados_mestre():
    assert find_transition(S.RASCUNHO, S.PENDENTE_COMPRAS)
    assert find_transition(S.PENDENTE_COMPRAS, S.PENDENTE_DADOS_MESTRE)
    assert find_transition(S.PENDENTE_DADOS_MESTRE, S.APROVADO_PARA_SAP)
    assert find_transition(S.APROVADO_PARA_SAP, S.CONCLUIDO_NO_SAP)


def test_nao_ha_atalhos_nem_saltos():
    proibidas = [
        (S.RASCUNHO, S.PENDENTE_DADOS_MESTRE),
        (S.RASCUNHO, S.APROVADO_PARA_SAP),
        (S.PENDENTE_COMPRAS, S.APROVADO_PARA_SAP),
        (S.DEVOLVIDO_PARA_CORRECAO, S.PENDENTE_DADOS_MESTRE),
        (S.PENDENTE_DADOS_MESTRE, S.CONCLUIDO_NO_SAP),
        (S.PENDENTE_DADOS_MESTRE, S.PENDENTE_COMPRAS),
    ]
    for origem, destino in proibidas:
        assert find_transition(origem, destino) is None, (origem, destino)


def test_concluido_e_estado_final():
    assert transitions_from(S.CONCLUIDO_NO_SAP) == []


def test_aprovar_e_concluir_exigem_permissoes_de_dados_mestre():
    assert find_transition(S.PENDENTE_DADOS_MESTRE, S.APROVADO_PARA_SAP).permission == Permission.MASTERDATA_APPROVE
    assert find_transition(S.APROVADO_PARA_SAP, S.CONCLUIDO_NO_SAP).permission == Permission.MASTERDATA_REGISTER_SAP_CODE


def test_devolver_exige_observacao():
    for origem in (S.PENDENTE_COMPRAS, S.PENDENTE_DADOS_MESTRE):
        assert find_transition(origem, S.DEVOLVIDO_PARA_CORRECAO).requires_note


def test_submissao_so_pelo_autor():
    assert find_transition(S.RASCUNHO, S.PENDENTE_COMPRAS).owner_only
    assert find_transition(S.DEVOLVIDO_PARA_CORRECAO, S.PENDENTE_COMPRAS).owner_only


def test_transicoes_unicas():
    pares = [(t.source, t.target) for t in TRANSITIONS]
    assert len(pares) == len(set(pares))


def test_so_ha_transicoes_para_pares_listados():
    validos = {(t.source, t.target) for t in TRANSITIONS}
    for a, b in itertools.product(S, S):
        assert (find_transition(a, b) is not None) == ((a, b) in validos)
