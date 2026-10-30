from dataclasses import dataclass

import pytest

from app.domain.access import can_edit_commercial, can_edit_sap_fields, can_edit_technical, can_view_request
from app.domain.enums import Department, RequestStatus
from app.domain.errors import PermissionDenied
from app.domain.permissions import Permission, has_permission, permissions_for, require_permission


@dataclass
class Fake:
    id: int
    username: str = "u"
    department: Department | None = None
    is_admin: bool = False


TEC = Fake(1, department=Department.TECNICOS_LOGISTICA)
COM = Fake(2, department=Department.COMPRAS)
DM = Fake(3, department=Department.DADOS_MESTRE)
ADMIN = Fake(4, department=None, is_admin=True)

MASTERDATA_ONLY = [
    Permission.MASTERDATA_APPROVE,
    Permission.MASTERDATA_EXPORT_SAP,
    Permission.MASTERDATA_REGISTER_SAP_CODE,
    Permission.MASTERDATA_EDIT_SAP_FIELDS,
]


@pytest.mark.parametrize("perm", MASTERDATA_ONLY)
def test_apenas_dados_mestre_aprova_exporta_e_regista_sap(perm):
    assert has_permission(DM, perm)
    for outro in (TEC, COM, ADMIN):
        assert not has_permission(outro, perm)


def test_administrador_nao_tem_autoridade_sobre_materiais():
    perms = permissions_for(ADMIN)
    assert perms == {Permission.MANAGE_USERS, Permission.VIEW_AUDIT_LOG}
    assert not has_permission(ADMIN, Permission.REQUEST_CREATE)


def test_administrador_com_departamento_nao_ganha_aprovacao():
    admin_tec = Fake(5, department=Department.TECNICOS_LOGISTICA, is_admin=True)
    assert not has_permission(admin_tec, Permission.MASTERDATA_APPROVE)
    assert has_permission(admin_tec, Permission.MANAGE_USERS)


def test_require_permission_levanta_erro():
    with pytest.raises(PermissionDenied):
        require_permission(TEC, Permission.MASTERDATA_APPROVE)


def test_tecnicos_criam_e_compras_nao():
    assert has_permission(TEC, Permission.REQUEST_CREATE)
    assert not has_permission(COM, Permission.REQUEST_CREATE)
    assert not has_permission(DM, Permission.REQUEST_CREATE)


def test_visibilidade_rascunhos_so_do_autor():
    assert can_view_request(TEC, status=RequestStatus.RASCUNHO, created_by_id=1)
    assert not can_view_request(Fake(9, department=Department.TECNICOS_LOGISTICA), status=RequestStatus.RASCUNHO, created_by_id=1)
    assert not can_view_request(COM, status=RequestStatus.RASCUNHO, created_by_id=1)
    assert not can_view_request(DM, status=RequestStatus.RASCUNHO, created_by_id=1)


def test_compras_e_dados_mestre_veem_submetidas():
    assert can_view_request(COM, status=RequestStatus.PENDENTE_COMPRAS, created_by_id=1)
    assert can_view_request(DM, status=RequestStatus.PENDENTE_DADOS_MESTRE, created_by_id=1)


def test_edicao_por_estado_e_departamento():
    assert can_edit_technical(TEC, status=RequestStatus.RASCUNHO, created_by_id=1)
    assert can_edit_technical(TEC, status=RequestStatus.DEVOLVIDO_PARA_CORRECAO, created_by_id=1)
    assert not can_edit_technical(TEC, status=RequestStatus.PENDENTE_COMPRAS, created_by_id=1)
    assert not can_edit_technical(TEC, status=RequestStatus.RASCUNHO, created_by_id=99)
    assert can_edit_commercial(COM, status=RequestStatus.PENDENTE_COMPRAS)
    assert not can_edit_commercial(COM, status=RequestStatus.PENDENTE_DADOS_MESTRE)
    assert not can_edit_commercial(DM, status=RequestStatus.PENDENTE_COMPRAS)
    assert can_edit_sap_fields(DM, status=RequestStatus.PENDENTE_DADOS_MESTRE)
    assert not can_edit_sap_fields(COM, status=RequestStatus.PENDENTE_DADOS_MESTRE)
