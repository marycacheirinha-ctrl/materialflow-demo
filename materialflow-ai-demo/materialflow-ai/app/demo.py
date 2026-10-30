"""Modo de demonstração: base de dados local simples e dados FICTÍCIOS.

Só para mostrar o fluxo a colegas num alojamento gratuito. Os dados perdem-se quando a aplicação
reinicia e nunca devem ser dados reais da empresa. É recusado com APP_ENV=production.
"""

from sqlalchemy import func, select

from app.config import ConfigError, get_settings
from app.db import models
from app.db.base import Base
from app.db.models import User
from app.db.session import get_engine, session_scope
from app.domain.enums import CharacteristicSource, Department, RequestStatus
from app.security import passwords
from app.security.password_policy import validate_password_strength
from app.services import categories, requests, users
from app.services.auth import to_current_user
from app.utils import clock

DEMO_ACCOUNTS = [
    ("demo.tecnico", "Técnico (demonstração)", Department.TECNICOS_LOGISTICA),
    ("demo.compras", "Compras (demonstração)", Department.COMPRAS),
    ("demo.dadosmestre", "Dados Mestre (demonstração)", Department.DADOS_MESTRE),
]
ADMIN_ACCOUNT = ("demo.admin", "Administrador (demonstração)")

PARTS = [
    ("Resistência de aquecimento da caldeira, 2400 W, 230 V", "RESISTENCIA", "RESISTÊNCIA 2400W 230V",
     "HEATING ELEMENT 2400W 230V", [("Potência", "2400", "W"), ("Tensão", "230", "V")]),
    ("Eletroválvula de 2 vias para circuito de água", "ELETROVALVULA", "ELETROVÁLVULA 2 VIAS",
     "2-WAY SOLENOID VALVE", [("Número de vias", "2", None)]),
    ("Caixa para recolha de borras de café", "OUTRO", "CAIXA DE BORRAS", "COFFEE GROUNDS BOX", []),
]
OFFER = {"supplier_name": "Fornecedor Exemplo, Lda.", "purchase_price": "12,50", "currency": "EUR", "purchase_unit": "UN"}


def ensure_ready() -> None:
    """Cria o esquema e os dados fictícios, se ainda não existirem. Idempotente."""
    settings = get_settings()
    if not settings.demo_mode:
        return
    password = settings.demo_password
    if not password:
        raise ConfigError(
            "Defina o segredo DEMO_PASSWORD (a palavra-passe das contas de demonstração, com pelo menos 12 caracteres)."
        )
    problems = validate_password_strength(password)
    if problems:
        raise ConfigError("DEMO_PASSWORD não é válida: " + " ".join(problems))

    Base.metadata.create_all(get_engine())
    with session_scope() as session:
        categories.ensure_default_categories(session)
        if session.scalar(select(func.count()).select_from(User)) == 0:
            _seed(session, password)


def _seed(session, password: str) -> None:
    admin_row = User(
        username=ADMIN_ACCOUNT[0], full_name=ADMIN_ACCOUNT[1], email=f"{ADMIN_ACCOUNT[0]}@exemplo.invalid",
        password_hash=passwords.hash_password(password), department=None, is_admin=True,
        must_change_password=False, password_changed_at=clock.now(),
    )
    session.add(admin_row)
    session.flush()
    admin = to_current_user(admin_row)

    actors = {}
    for username, name, department in DEMO_ACCOUNTS:
        users.create_user(
            session, admin, username=username, full_name=name, email=f"{username}@exemplo.invalid",
            password=password, department=department, must_change_password=False,
        )
        actors[department] = to_current_user(session.scalar(select(User).where(User.username == username)))
    tecnico = actors[Department.TECNICOS_LOGISTICA]
    compras = actors[Department.COMPRAS]

    by_code = {c.code: c for c in categories.list_categories(session)}
    created = []
    for original, code, pt, en, chars in PARTS:
        req = requests.create_request(
            session, tecnico,
            {"original_description": original, "category_id": by_code[code].id, "description_pt": pt, "description_en": en},
        )
        if chars:
            requests.set_characteristics(
                session, tecnico, req.id,
                [{"label": n, "value": v, "unit": u, "source": CharacteristicSource.DESCRICAO_ORIGINAL} for n, v, u in chars],
            )
        created.append(req)

    # Estados variados, para cada departamento ter algo para ver.
    requests.transition(session, tecnico, created[0].id, RequestStatus.PENDENTE_COMPRAS)
    requests.transition(session, tecnico, created[1].id, RequestStatus.PENDENTE_COMPRAS)
    requests.add_offer(session, compras, created[1].id, OFFER)
    requests.transition(session, compras, created[1].id, RequestStatus.PENDENTE_DADOS_MESTRE)
    # created[2] fica em rascunho, para o técnico.


__all__ = ["ensure_ready", "models"]
