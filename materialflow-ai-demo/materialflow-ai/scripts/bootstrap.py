"""Dados de referência necessários ao arranque (idempotente). Não cria utilizadores nem credenciais."""

from app.config import get_settings
from app.db.session import session_scope
from app.logging_setup import configure_logging
from app.services.categories import ensure_default_categories


def main() -> None:
    configure_logging(get_settings().log_level)
    with session_scope() as session:
        created = ensure_default_categories(session)
    print(f"Categorias de componentes verificadas ({created} criada(s)).")


if __name__ == "__main__":
    main()
