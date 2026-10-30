"""Relógio central. Usar `clock.now()` para que os testes controlem o tempo."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
