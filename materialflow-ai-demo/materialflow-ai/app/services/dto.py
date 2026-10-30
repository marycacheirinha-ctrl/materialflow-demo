from dataclasses import dataclass

from app.domain.enums import Department


@dataclass(frozen=True)
class CurrentUser:
    """Utilizador autenticado, desligado da sessão da base de dados. Cumpre o protocolo `Actor`."""

    id: int
    username: str
    full_name: str
    department: Department | None
    is_admin: bool
    must_change_password: bool = False
