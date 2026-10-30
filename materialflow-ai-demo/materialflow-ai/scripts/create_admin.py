"""Cria o administrador técnico inicial. A palavra-passe é pedida no terminal (nunca fica no código).

Uso:  python -m scripts.create_admin
Em alternativa (automação): defina ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_FULL_NAME e ADMIN_PASSWORD.
O administrador técnico gere contas, mas não tem autoridade para aprovar materiais.
"""

import getpass
import os
import sys

from sqlalchemy import func, select

from app.db.models import User
from app.db.session import session_scope
from app.domain.errors import DomainError
from app.security import passwords
from app.security.password_policy import validate_password_strength
from app.services import audit
from app.utils import clock


def main() -> int:
    username = (os.getenv("ADMIN_USERNAME") or input("Nome de utilizador: ")).strip().lower()
    full_name = (os.getenv("ADMIN_FULL_NAME") or input("Nome completo: ")).strip()
    email = (os.getenv("ADMIN_EMAIL") or input("Email: ")).strip().lower()
    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Palavra-passe: ")
        if getpass.getpass("Repita a palavra-passe: ") != password:
            print("As palavras-passe não coincidem.")
            return 1
    problems = validate_password_strength(password, username=username)
    if problems:
        print("\n".join(problems))
        return 1
    try:
        with session_scope() as session:
            if session.scalar(select(func.count()).select_from(User).where(User.username == username)):
                print("Esse nome de utilizador já existe.")
                return 1
            user = User(
                username=username,
                full_name=full_name,
                email=email,
                password_hash=passwords.hash_password(password),
                department=None,
                is_admin=True,
                must_change_password=False,
                password_changed_at=clock.now(),
            )
            session.add(user)
            session.flush()
            audit.record(session, "ADMIN_CRIADO_POR_SCRIPT", username=username, entity_type="user", entity_id=user.id)
    except DomainError as exc:
        print(exc)
        return 1
    print(f"Administrador técnico «{username}» criado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
