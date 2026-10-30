"""Política de palavras-passe (comprimento e lista de palavras-passe comuns)."""

from app.config import get_settings

MAX_PASSWORD_LENGTH = 128

COMMON_PASSWORDS = frozenset(
    {
        "passwordpassword",
        "password1234",
        "123456789012",
        "qwertyuiop12",
        "palavrapasse",
        "palavra-passe",
        "administrator",
        "welcome12345",
        "changeme1234",
        "letmein12345",
        "senha1234567",
        "materialflow",
    }
)


def validate_password_strength(
    password: str, *, username: str | None = None, min_length: int | None = None
) -> list[str]:
    minimum = min_length if min_length is not None else get_settings().password_min_length
    errors: list[str] = []
    if len(password) < minimum:
        errors.append(f"A palavra-passe tem de ter pelo menos {minimum} caracteres.")
    if len(password) > MAX_PASSWORD_LENGTH:
        errors.append(f"A palavra-passe não pode ter mais de {MAX_PASSWORD_LENGTH} caracteres.")
    if password.strip() == "":
        errors.append("A palavra-passe não pode ser só espaços.")
    if len(set(password)) < 5:
        errors.append("A palavra-passe é demasiado repetitiva.")
    if password.lower() in COMMON_PASSWORDS:
        errors.append("A palavra-passe é demasiado comum.")
    if username and len(username) >= 3 and username.lower() in password.lower():
        errors.append("A palavra-passe não pode conter o nome de utilizador.")
    return errors
