import pytest

from app.domain.enums import Department, RequestStatus
from app.domain.errors import ConflictError, NotFoundError, PermissionDenied, ValidationError
from app.services import requests, users
from tests.integration.conftest import PASSWORD

NEW = dict(username="novo.user", full_name="Novo Utilizador", email="novo@exemplo.invalid", password=PASSWORD)


def test_administrador_cria_conta(session, admin):
    user = users.create_user(session, admin, department=Department.COMPRAS, **NEW)
    assert user.username == "novo.user" and user.password_hash.startswith("$argon2id$")
    assert user.must_change_password


def test_outros_perfis_nao_gerem_contas(session, tec, compras, dm):
    for actor in (tec, compras, dm):
        with pytest.raises(PermissionDenied):
            users.create_user(session, actor, department=Department.COMPRAS, **NEW)


def test_validacoes_na_criacao(session, admin):
    with pytest.raises(ValidationError):
        users.create_user(session, admin, department=None, **NEW)  # sem departamento nem admin
    with pytest.raises(ValidationError):
        users.create_user(session, admin, department=Department.COMPRAS, **{**NEW, "password": "curta"})
    with pytest.raises(ValidationError):
        users.create_user(session, admin, department=Department.COMPRAS, **{**NEW, "email": "invalido"})
    users.create_user(session, admin, department=Department.COMPRAS, **NEW)
    with pytest.raises(ConflictError):
        users.create_user(session, admin, department=Department.COMPRAS, **NEW)


def test_nao_se_remove_o_ultimo_administrador(session, admin):
    with pytest.raises(ConflictError):
        users.update_user(session, admin, admin.id, department=Department.COMPRAS, is_admin=False, is_active=True)
    with pytest.raises(ConflictError):
        users.update_user(session, admin, admin.id, department=None, is_admin=True, is_active=False)


def test_administrador_nao_tem_autoridade_sobre_materiais(session, admin, tec, compras, dm):
    """O administrador técnico gere contas, mas não cria, aprova nem conclui materiais."""
    with pytest.raises(PermissionDenied):
        requests.create_request(session, admin, {"original_description": "peça"})
    req = requests.create_request(session, tec, {"original_description": "peça"})
    for target in (RequestStatus.PENDENTE_COMPRAS, RequestStatus.APROVADO_PARA_SAP):
        with pytest.raises(NotFoundError):  # nem sequer vê as solicitações
            requests.transition(session, admin, req.id, target)
