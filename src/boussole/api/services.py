"""Assemblage des dépendances de l'API (injectées, donc remplaçables en test)."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boussole.agents.catalog import Catalog, load_catalog
from boussole.config import AppConfig
from boussole.core.models import Base
from boussole.platform.llm_gateway.budget import BudgetedGateway, UsageLedger
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from boussole.platform.llm_gateway.port import ModelInfo
from boussole.platform.secrets import OPENROUTER_KEY, KeyringSecretStore, SecretStore
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import SettingsRepository, SqlUsageLedger

MODELS_TTL_S = 3600


@dataclass
class Services:
    catalog: Catalog
    repo: SettingsRepository
    ledger: UsageLedger
    secrets: SecretStore
    gateway_factory: Callable[[str], OpenRouterGateway]
    cap_cad: Decimal
    operator: str
    _models_cache: tuple[float, tuple[ModelInfo, ...]] | None = field(default=None, repr=False)

    def gateway(self) -> OpenRouterGateway | None:
        key = self.secrets.get(OPENROUTER_KEY)
        return self.gateway_factory(key) if key else None

    def budgeted_gateway(self) -> BudgetedGateway | None:
        inner = self.gateway()
        return BudgetedGateway(inner, self.ledger, self.cap_cad) if inner else None

    def models(self) -> tuple[ModelInfo, ...]:
        """Liste des modèles OpenRouter, mise en cache une heure (appel gratuit)."""
        if self._models_cache and time.monotonic() - self._models_cache[0] < MODELS_TTL_S:
            return self._models_cache[1]
        gateway = self.gateway()
        if gateway is None:
            return ()
        models = tuple(sorted(gateway.list_models(), key=lambda m: m.id))
        self._models_cache = (time.monotonic(), models)
        return models

    def forget_models(self) -> None:
        self._models_cache = None


def build_services(config: AppConfig) -> Services:
    if config.is_lightweight:
        Path(config.database_url.removeprefix("sqlite:///")).parent.mkdir(
            parents=True, exist_ok=True
        )
    engine = create_engine(config.database_url)
    if config.is_lightweight:
        Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    sessions = sessionmaker(engine, expire_on_commit=False)
    catalog = load_catalog(config.catalog_path)
    return Services(
        catalog=catalog,
        repo=SettingsRepository(sessions, catalog),
        ledger=SqlUsageLedger(sessions),
        secrets=KeyringSecretStore(),
        gateway_factory=lambda key: OpenRouterGateway(key, config.usd_to_cad),
        cap_cad=config.budget_cap_cad,
        operator=config.operator,
    )
