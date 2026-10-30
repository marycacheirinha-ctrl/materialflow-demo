import pytest

from app.config import ConfigError, reload_settings


@pytest.fixture
def clean_env(monkeypatch):
    for name in ("DATABASE_URL", "POSTGRES_HOST", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
                 "STORAGE_DIR", "DEMO_MODE", "DEMO_PASSWORD", "APP_ENV"):
        monkeypatch.delenv(name, raising=False)
    yield monkeypatch
    monkeypatch.undo()
    reload_settings()


def test_sem_modo_demo_exige_base_de_dados_configurada(clean_env):
    settings = reload_settings()
    assert settings.demo_mode is False
    with pytest.raises(ConfigError):
        settings.database_url()


def test_modo_demo_usa_sqlite_local_e_armazenamento_temporario(clean_env):
    clean_env.setenv("DEMO_MODE", "true")
    settings = reload_settings()
    assert settings.demo_mode is True
    assert settings.database_url().startswith("sqlite:///")
    assert "materialflow-demo-storage" in str(settings.storage_dir)


def test_modo_demo_respeita_base_de_dados_explicita(clean_env):
    clean_env.setenv("DEMO_MODE", "true")
    clean_env.setenv("DATABASE_URL", "sqlite:////tmp/outra.db")
    assert reload_settings().database_url() == "sqlite:////tmp/outra.db"


def test_modo_demo_recusado_em_producao(clean_env):
    clean_env.setenv("DEMO_MODE", "true")
    clean_env.setenv("APP_ENV", "production")
    with pytest.raises(ConfigError):
        reload_settings()
