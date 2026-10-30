"""Funções de validação partilhadas pelos serviços."""

from app.domain.errors import ValidationError


def clean_text(value: str | None, *, label: str, max_length: int, required: bool = False) -> str | None:
    text = " ".join((value or "").split())
    if not text:
        if required:
            raise ValidationError(f"O campo «{label}» é obrigatório.")
        return None
    if len(text) > max_length:
        raise ValidationError(f"O campo «{label}» excede o máximo de {max_length} caracteres.")
    return text
