"""Base de test migrée à neuf pour chaque session d'intégration."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine

ROOT = Path(__file__).resolve().parents[2]


def _alembic_config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "infra" / "migrations"))
    config.attributes["database_url"] = url
    return config


@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("BOUSSOLE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("BOUSSOLE_TEST_DATABASE_URL non défini")
    return url


@pytest.fixture(scope="session")
def alembic_config(database_url: str) -> Config:
    return _alembic_config(database_url)


@pytest.fixture(scope="session")
def engine(alembic_config: Config, database_url: str) -> Iterator[Engine]:
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")
    engine = create_engine(database_url)
    yield engine
    engine.dispose()
