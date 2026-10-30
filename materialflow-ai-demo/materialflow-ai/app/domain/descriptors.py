"""Normalização e validação dos descritivos (PT-PT e EN).

Máximo de 40 caracteres (com espaços), maiúsculas, sem ponto final.
Nunca se corta texto: se exceder o limite, devolve-se erro para obter uma versão mais curta.
"""

import re
import unicodedata
from dataclasses import dataclass

MAX_DESCRIPTOR_LENGTH = 40

_WHITESPACE = re.compile(r"\s+")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class DescriptorCheck:
    original: str
    normalized: str
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def length(self) -> int:
        return len(self.normalized)


def normalize_descriptor(text: str | None) -> str:
    """Espaços simplificados, maiúsculas e sem pontos finais. Não corta o texto."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    text = _WHITESPACE.sub(" ", text).strip()
    text = text.rstrip(".").rstrip()
    return text.upper()


def check_descriptor(text: str | None) -> DescriptorCheck:
    normalized = normalize_descriptor(text)
    errors: list[str] = []
    if not normalized:
        errors.append("não pode estar vazio")
    elif len(normalized) > MAX_DESCRIPTOR_LENGTH:
        errors.append(
            f"tem {len(normalized)} caracteres e o máximo é {MAX_DESCRIPTOR_LENGTH}; "
            "escreva ou peça uma versão mais curta"
        )
    if _CONTROL_CHARS.search(normalized):
        errors.append("contém caracteres inválidos")
    return DescriptorCheck(original=text or "", normalized=normalized, errors=tuple(errors))
