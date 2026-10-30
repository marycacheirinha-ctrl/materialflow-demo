"""Armazenamento privado de ficheiros no disco. Nunca servido diretamente pela web.

Os ficheiros são guardados por chave aleatória (nunca pelo nome original) e só são lidos
através dos serviços, depois da verificação de permissões.
"""

import re
import uuid
from pathlib import Path

from app.config import get_settings

_KEY = re.compile(r"^[0-9a-f]{32}$")


def _root() -> Path:
    root = get_settings().storage_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _path_for(key: str) -> Path:
    if not _KEY.match(key):
        raise ValueError("Chave de armazenamento inválida.")
    root = _root()
    path = (root / key[:2] / key).resolve()
    if root not in path.parents:
        raise ValueError("Caminho fora do armazenamento.")
    return path


def new_key() -> str:
    return uuid.uuid4().hex


def save(key: str, data: bytes) -> None:
    path = _path_for(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def read(key: str) -> bytes:
    return _path_for(key).read_bytes()


def delete(key: str) -> None:
    _path_for(key).unlink(missing_ok=True)
