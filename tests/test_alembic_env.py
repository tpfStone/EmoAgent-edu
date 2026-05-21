import importlib.util
from pathlib import Path


def _load_alembic_env():
    env_path = Path(__file__).resolve().parents[1] / "alembic" / "env.py"
    spec = importlib.util.spec_from_file_location("project_alembic_env", env_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_to_sync_database_url_converts_async_postgres():
    env = _load_alembic_env()

    assert (
        env.to_sync_database_url("postgresql+asyncpg://u:p@localhost/db")
        == "postgresql+psycopg2://u:p@localhost/db"
    )


def test_to_sync_database_url_converts_async_sqlite():
    env = _load_alembic_env()

    assert (
        env.to_sync_database_url("sqlite+aiosqlite:///./local-dev.sqlite")
        == "sqlite:///./local-dev.sqlite"
    )
