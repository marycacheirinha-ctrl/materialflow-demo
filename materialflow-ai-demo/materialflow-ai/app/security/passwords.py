"""Hashing de palavras-passe com Argon2id."""

from functools import lru_cache

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import get_settings


@lru_cache(maxsize=8)
def _hasher(time_cost: int, memory_kib: int, parallelism: int) -> PasswordHasher:
    return PasswordHasher(time_cost=time_cost, memory_cost=memory_kib, parallelism=parallelism, type=Type.ID)


def get_hasher() -> PasswordHasher:
    s = get_settings()
    return _hasher(s.argon2_time_cost, s.argon2_memory_kib, s.argon2_parallelism)


def hash_password(password: str) -> str:
    return get_hasher().hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return bool(get_hasher().verify(password_hash, password))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return get_hasher().check_needs_rehash(password_hash)


@lru_cache(maxsize=8)
def _dummy(time_cost: int, memory_kib: int, parallelism: int) -> str:
    return _hasher(time_cost, memory_kib, parallelism).hash("palavra-passe-ficticia-para-igualar-tempos")


def dummy_hash() -> str:
    """Hash fictício para igualar o tempo de resposta quando o utilizador não existe."""
    s = get_settings()
    return _dummy(s.argon2_time_cost, s.argon2_memory_kib, s.argon2_parallelism)
