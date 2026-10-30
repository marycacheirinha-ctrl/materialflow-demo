"""Dados de demonstração FICTÍCIOS, só para testes locais. Nunca usar em produção.

Cria um utilizador por departamento e algumas solicitações de exemplo. Não há palavras-passe
no código: são geradas ao acaso e mostradas uma única vez no terminal.

Uso:  python -m scripts.seed_demo
"""

import secrets
import sys

from sqlalchemy import func, select

from app.config import get_settings
from app.db.models import MaterialRequest, User
from app.db.session import session_scope
from app.domain.enums import CharacteristicSource, Department, RequestStatus
from app.services import categories, requests, users
from app.services.auth import to_current_user

DEMO_USERS = [
    ("demo.tecnico", "Técnico Demonstração", Department.TECNICOS_LOGISTICA),
    ("demo.compras", "Compras Demonstração", Department.COMPRAS),
    ("demo.dadosmestre", "Dados Mestre Demonstração", Department.DADOS_MESTRE),
]

DEMO_PARTS = [
    ("Resistência de aquecimento da caldeira, 2400 W, 230 V", "RESISTENCIA", "RESISTÊNCIA 2400W 230V", "HEATING ELEMENT 2400W 230V",
     [("Potência", "2400", "W"), ("Tensão", "230", "V")]),
    ("Eletroválvula de 2 vias para circuito de água", "ELETROVALVULA", "ELETROVÁLVULA 2 VIAS", "2-WAY SOLENOID VALVE",
     [("Número de vias", "2", None)]),
    ("Caixa para recolha de borras de café", "OUTRO", "CAIXA DE BORRAS", "COFFEE GROUNDS BOX", []),
]


def main() -> int:
    if get_settings().is_production:
        print("Recusado: os dados de demonstração não podem ser criados em produção.")
        return 1
    credentials: list[tuple[str, str]] = []
    with session_scope() as session:
        if session.scalar(select(func.count()).select_from(User).where(User.username.like("demo.%"))):
            print("Os dados de demonstração já existem.")
            return 0
        categories.ensure_default_categories(session)
        admin_row = session.scalar(select(User).where(User.is_admin.is_(True), User.is_active.is_(True)))
        if admin_row is None:
            print("Crie primeiro o administrador: python -m scripts.create_admin")
            return 1
        admin = to_current_user(admin_row)
        created = {}
        for username, name, department in DEMO_USERS:
            password = secrets.token_urlsafe(12) + "aA1"
            users.create_user(
                session, admin, username=username, full_name=name, email=f"{username}@exemplo.invalid",
                password=password, department=department, must_change_password=False,
            )
            credentials.append((username, password))
            created[username] = to_current_user(session.scalar(select(User).where(User.username == username)))

        tecnico = created["demo.tecnico"]
        cats = {c.code: c for c in categories.list_categories(session)}
        for original, cat, pt, en, chars in DEMO_PARTS:
            req = requests.create_request(
                session, tecnico,
                {"original_description": original, "category_id": cats[cat].id, "description_pt": pt, "description_en": en},
            )
            if chars:
                requests.set_characteristics(
                    session, tecnico, req.id,
                    [{"label": name, "value": value, "unit": unit, "source": CharacteristicSource.DESCRICAO_ORIGINAL} for name, value, unit in chars],
                )
        # Uma solicitação já submetida, para Compras ver algo.
        first = session.scalar(select(MaterialRequest).order_by(MaterialRequest.id))
        requests.transition(session, tecnico, first.id, RequestStatus.PENDENTE_COMPRAS)

    print("Utilizadores de demonstração (guarde agora, não voltam a ser mostradas):")
    for username, password in credentials:
        print(f"  {username}  {password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
