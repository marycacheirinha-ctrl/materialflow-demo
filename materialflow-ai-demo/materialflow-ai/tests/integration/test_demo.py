import pytest
from sqlalchemy import func, select

from app import demo
from app.config import ConfigError, reload_settings
from app.db import session as db_session
from app.db.models import MaterialRequest, User
from app.domain.enums import RequestStatus
from app.services import auth


def _demo_env(monkeypatch, password="uma frase longa e unica 2026"):
    monkeypatch.setenv("DEMO_MODE", "true")
    if password:
        monkeypatch.setenv("DEMO_PASSWORD", password)
    else:
        monkeypatch.delenv("DEMO_PASSWORD", raising=False)
    reload_settings()


def test_exige_palavra_passe_de_demonstracao(monkeypatch):
    _demo_env(monkeypatch, password=None)
    with pytest.raises(ConfigError):
        demo.ensure_ready()
    _demo_env(monkeypatch, password="curta")
    with pytest.raises(ConfigError):
        demo.ensure_ready()


def test_cria_contas_e_pecas_ficticias_uma_so_vez(monkeypatch):
    _demo_env(monkeypatch)
    demo.ensure_ready()
    demo.ensure_ready()  # idempotente
    with db_session.session_scope() as s:
        assert s.scalar(select(func.count()).select_from(User)) == 4
        statuses = sorted(r.status for r in s.scalars(select(MaterialRequest)))
    assert statuses == sorted([RequestStatus.RASCUNHO, RequestStatus.PENDENTE_COMPRAS, RequestStatus.PENDENTE_DADOS_MESTRE])


def test_login_nas_contas_de_demonstracao(monkeypatch):
    _demo_env(monkeypatch)
    demo.ensure_ready()
    with db_session.session_scope() as s:
        user, _ = auth.authenticate(s, "demo.dadosmestre", "uma frase longa e unica 2026")
    assert user.department.value == "DADOS_MESTRE" and not user.must_change_password
