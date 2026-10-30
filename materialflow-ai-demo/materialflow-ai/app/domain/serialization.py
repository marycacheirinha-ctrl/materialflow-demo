"""Conversão de valores para JSON seguro (auditoria e histórico)."""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


def jsonable(value: Any, *, max_string: int = 2000) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, Enum):
        return jsonable(value.value, max_string=max_string)
    if isinstance(value, str):
        return value if len(value) <= max_string else value[: max_string - 3] + "..."
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(k): jsonable(v, max_string=max_string) for k, v in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [jsonable(v, max_string=max_string) for v in value]
    return str(value)[:max_string]
