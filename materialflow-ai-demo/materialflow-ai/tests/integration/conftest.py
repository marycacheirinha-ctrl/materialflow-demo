"""Fixtures de integração: base de dados SQLite temporária e utilizadores de cada departamento.

Estes testes exigem as dependências do projeto (SQLAlchemy, argon2-cffi). Sem elas, são ignorados.
"""

import datetime as dt

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("argon2")

from app.config import reload_settings  # noqa: E402
from app.db import session as db_session  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models import User  # noqa: E402
from app.domain.enums import Department  # noqa: E402
from app.security import passwords  # noqa: E402
from app.services import categories  # noqa: E402
from app.services.auth import to_current_user  # noqa: E402
from app.utils import clock  # noqa: E402

PASSWORD = "uma frase longa e unica 2026"


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'teste.db'}")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    # Argon2id com custo mínimo, só para os testes ficarem rápidos.
    monkeypatch.setenv("ARGON2_TIME_COST", "1")
    monkeypatch.setenv("ARGON2_MEMORY_KIB", "8")
    monkeypatch.setenv("ARGON2_PARALLELISM", "1")
    reload_settings()
    passwords._hasher.cache_clear()
    passwords._dummy.cache_clear()
    db_session.reset_engine_cache()
    Base.metadata.create_all(db_session.get_engine())
    yield
    db_session.get_engine().dispose()
    db_session.reset_engine_cache()


@pytest.fixture
def session():
    with db_session.session_scope() as s:
        categories.ensure_default_categories(s)
    with db_session.session_scope() as s:
        yield s


@pytest.fixture
def fake_clock(monkeypatch):
    class Clock:
        def __init__(self):
            self.t = dt.datetime(2026, 10, 29, 12, 0, tzinfo=dt.UTC)

        def advance(self, **kwargs):
            self.t += dt.timedelta(**kwargs)

    c = Clock()
    monkeypatch.setattr(clock, "now", lambda: c.t)
    return c


def make_user(session, username, department=None, *, is_admin=False, active=True, password=PASSWORD):
    user = User(
        username=username,
        full_name=username.title(),
        email=f"{username}@exemplo.invalid",
        password_hash=passwords.hash_password(password),
        department=department,
        is_admin=is_admin,
        is_active=active,
        password_changed_at=clock.now(),
    )
    session.add(user)
    session.flush()
    return user


@pytest.fixture
def tec(session):
    return to_current_user(make_user(session, "tecnico", Department.TECNICOS_LOGISTICA))


@pytest.fixture
def tec2(session):
    return to_current_user(make_user(session, "tecnico2", Department.TECNICOS_LOGISTICA))


@pytest.fixture
def compras(session):
    return to_current_user(make_user(session, "compras", Department.COMPRAS))


@pytest.fixture
def dm(session):
    return to_current_user(make_user(session, "dadosmestre", Department.DADOS_MESTRE))


@pytest.fixture
def admin(session):
    return to_current_user(make_user(session, "administrador", None, is_admin=True))
