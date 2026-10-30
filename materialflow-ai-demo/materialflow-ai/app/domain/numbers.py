"""Leitura e apresentação de números decimais no formato português."""

import re
from decimal import Decimal

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")


def parse_decimal(raw: str | None, *, field: str = "valor") -> Decimal | None:
    """Lê «12,50», «1.234,56», «1,234.56» ou «12.5». Vazio devolve None.

    Com os dois separadores, o último que aparece é o decimal. Com um só, é decimal.
    """
    if raw is None:
        return None
    text = raw.strip().replace(" ", "").replace(" ", "")
    if text == "":
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    if not _NUMBER.match(text):
        raise ValueError(f"O campo «{field}» não é um número válido.")
    return Decimal(text)


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.normalize(), "f").replace(".", ",")
