"""A migração inicial tem de produzir exatamente o esquema descrito pelos modelos."""

from pathlib import Path

import pytest

pytest.importorskip("alembic")

from alembic.autogenerate import compare_metadata  # noqa: E402
from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from sqlalchemy import create_engine, inspect  # noqa: E402

from alembic import command  # noqa: E402
from app.config import reload_settings  # noqa: E402
from app.db import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    return cfg


def test_migracao_coincide_com_os_modelos_e_reverte(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'migracao.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    reload_settings()
    command.upgrade(_config(), "head")

    engine = create_engine(url)
    with engine.connect() as connection:
        diffs = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diffs == [], f"A migração difere dos modelos: {diffs}"

    command.downgrade(_config(), "base")
    assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
    engine.dispose()
