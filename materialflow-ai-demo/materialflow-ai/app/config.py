"""Configuração da aplicação, lida apenas de variáveis de ambiente.

Nenhuma credencial tem valor por omissão no código.
"""

import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class ConfigError(RuntimeError):
    """Configuração em falta ou inválida."""


def _text(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _int(name: str, default: int) -> int:
    raw = _text(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"A variável {name} tem de ser um número inteiro.") from exc


def _bool(name: str, default: bool = False) -> bool:
    raw = _text(name)
    if raw is None:
        return default
    return raw.lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class Settings:
    app_env: str
    log_level: str
    app_base_url: str
    database_url_raw: str | None
    pg_host: str | None
    pg_port: int
    pg_db: str | None
    pg_user: str | None
    pg_password: str | None
    storage_dir: Path
    session_idle_minutes: int
    session_absolute_hours: int
    max_failed_logins: int
    failed_login_window_minutes: int
    lockout_minutes: int
    password_min_length: int
    reset_token_minutes: int
    argon2_time_cost: int
    argon2_memory_kib: int
    argon2_parallelism: int
    max_image_mb: int
    max_pdf_mb: int
    max_attachments_per_request: int
    # Modo de demonstração: base de dados local simples e dados fictícios (nunca em produção).
    demo_mode: bool
    demo_password: str | None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def max_image_bytes(self) -> int:
        return self.max_image_mb * 1024 * 1024

    @property
    def max_pdf_bytes(self) -> int:
        return self.max_pdf_mb * 1024 * 1024

    def database_url(self) -> str:
        """URL da base de dados: DATABASE_URL ou construída com os componentes POSTGRES_*."""
        if self.database_url_raw:
            return self.database_url_raw
        if self.demo_mode and not self.pg_host:
            return f"sqlite:///{Path(tempfile.gettempdir()) / 'materialflow-demo.db'}"
        if not all([self.pg_host, self.pg_db, self.pg_user, self.pg_password]):
            raise ConfigError(
                "Defina DATABASE_URL ou, em alternativa, POSTGRES_HOST, POSTGRES_DB, "
                "POSTGRES_USER e POSTGRES_PASSWORD."
            )
        from sqlalchemy.engine import URL

        url = URL.create(
            "postgresql+psycopg",
            username=self.pg_user,
            password=self.pg_password,
            host=self.pg_host,
            port=self.pg_port,
            database=self.pg_db,
        )
        return url.render_as_string(hide_password=False)


def _load() -> Settings:
    app_env = (_text("APP_ENV", "development") or "development").lower()
    demo_mode = _bool("DEMO_MODE")
    if demo_mode and app_env == "production":
        raise ConfigError("O modo de demonstração (DEMO_MODE) não pode ser usado com APP_ENV=production.")
    default_storage = str(Path(tempfile.gettempdir()) / "materialflow-demo-storage") if demo_mode else "./storage"
    return Settings(
        app_env=app_env,
        log_level=(_text("LOG_LEVEL", "INFO") or "INFO").upper(),
        app_base_url=_text("APP_BASE_URL", "http://localhost:8501") or "http://localhost:8501",
        database_url_raw=_text("DATABASE_URL"),
        pg_host=_text("POSTGRES_HOST"),
        pg_port=_int("POSTGRES_PORT", 5432),
        pg_db=_text("POSTGRES_DB"),
        pg_user=_text("POSTGRES_USER"),
        pg_password=os.getenv("POSTGRES_PASSWORD") or None,
        storage_dir=Path(_text("STORAGE_DIR", default_storage) or default_storage),
        session_idle_minutes=_int("SESSION_IDLE_MINUTES", 30),
        session_absolute_hours=_int("SESSION_ABSOLUTE_HOURS", 8),
        max_failed_logins=_int("MAX_FAILED_LOGINS", 5),
        failed_login_window_minutes=_int("FAILED_LOGIN_WINDOW_MINUTES", 15),
        lockout_minutes=_int("LOCKOUT_MINUTES", 15),
        password_min_length=_int("PASSWORD_MIN_LENGTH", 12),
        reset_token_minutes=_int("RESET_TOKEN_MINUTES", 30),
        argon2_time_cost=_int("ARGON2_TIME_COST", 3),
        argon2_memory_kib=_int("ARGON2_MEMORY_KIB", 65536),
        argon2_parallelism=_int("ARGON2_PARALLELISM", 4),
        max_image_mb=_int("MAX_IMAGE_MB", 10),
        max_pdf_mb=_int("MAX_PDF_MB", 20),
        max_attachments_per_request=_int("MAX_ATTACHMENTS_PER_REQUEST", 20),
        demo_mode=demo_mode,
        demo_password=os.getenv("DEMO_PASSWORD") or None,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _load()


def reload_settings() -> Settings:
    """Volta a ler o ambiente (usado nos testes)."""
    get_settings.cache_clear()
    return get_settings()
