"""Tokens aleatórios. Só o hash SHA-256 é guardado na base de dados."""

import hashlib
import secrets


def generate_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
