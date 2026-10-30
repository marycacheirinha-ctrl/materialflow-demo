"""Erros de regra de negócio. As mensagens são apresentáveis ao utilizador (pt-PT)."""


class DomainError(Exception):
    """Base dos erros esperados, com mensagem pronta a mostrar."""


class ValidationError(DomainError):
    def __init__(self, errors: list[str] | str):
        if isinstance(errors, str):
            errors = [errors]
        self.errors: list[str] = list(errors)
        super().__init__(" ".join(self.errors))


class PermissionDenied(DomainError):
    """O utilizador não tem permissão para a operação."""


class NotFoundError(DomainError):
    """Registo inexistente (ou que o utilizador não pode ver)."""


class ConflictError(DomainError):
    """A operação não é possível no estado atual dos dados."""


class AuthenticationError(DomainError):
    """Falha de autenticação."""


class AccountLockedError(AuthenticationError):
    def __init__(self, retry_after_minutes: int):
        self.retry_after_minutes = retry_after_minutes
        super().__init__(
            f"Demasiadas tentativas falhadas. Tente novamente dentro de {retry_after_minutes} minuto(s)."
        )
