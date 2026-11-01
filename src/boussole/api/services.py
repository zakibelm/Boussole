"""Assemblage des dépendances de l'API (injectées, donc remplaçables en test)."""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from functools import cache
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

from boussole.agents.answer import Answerer, MissingApiKeyError
from boussole.agents.catalog import Catalog, load_catalog
from boussole.agents.pmbok_skills import PmbokSkills, load_pmbok_skills
from boussole.config import AppConfig
from boussole.core.database import make_engine
from boussole.core.enums import ActionClass
from boussole.core.models import Base
from boussole.platform.audit.log import (
    AuditEvent,
    AuditLog,
    MissingSigningKeyError,
    create_audit_table,
)
from boussole.platform.guardrails.gate import ActionGate
from boussole.platform.guardrails.policy import load_policy
from boussole.platform.llm_gateway.budget import BudgetedGateway, UsageLedger
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from boussole.platform.llm_gateway.port import ModelInfo
from boussole.platform.memory_rag.memory import RagMemory
from boussole.platform.secrets import OPENROUTER_KEY, KeyringSecretStore, SecretStore
from boussole.platform.settings_store.repository import SettingsRepository, SqlUsageLedger
from boussole.projects.assistant import ProjectAssistant
from boussole.projects.repository import ProjectRepository

MODELS_TTL_S = 3600
# Parties du livre sur le choix de l'approche, pour la proposition du sélecteur
INTAKE_PARTS = ("standard.approaches", "guide.tailoring")


@dataclass
class Services:
    catalog: Catalog
    repo: SettingsRepository
    ledger: UsageLedger
    secrets: SecretStore
    gateway_factory: Callable[[str], OpenRouterGateway]
    cap_cad: Decimal
    operator: str
    projects: ProjectAssistant | None = None
    trust_proxy_user: bool = False
    roles: dict[str, str] = field(default_factory=dict)
    default_role: str = "pmo"
    audit: AuditLog | None = None
    task_cap_cad: Decimal | None = None
    _models_cache: tuple[float, tuple[ModelInfo, ...]] | None = field(default=None, repr=False)

    def record_settings_change(
        self, request: Request, action: str, details: dict[str, object]
    ) -> None:
        """Journalise une écriture de Paramètres AVANT son effet (échec fermé) :
        qui, avec quel rôle, sur quoi. Jamais la clé elle-même."""
        if self.audit is None:
            raise MissingSigningKeyError("Journal d'audit indisponible : modification refusée.")
        payload: dict[str, object] = {
            "by": self.operator_for(request),
            "role": self.role_for(request),
            **details,
        }
        self.audit.append(
            AuditEvent(
                uuid.uuid4(),
                "settings",
                f"settings.{action}",
                ActionClass.REVERSIBLE_WRITE,
                None,
                payload,
            )
        )

    def operator_for(self, request: Request) -> str:
        """Compte authentifié par nginx (en-tête posé par nginx, jamais par le client),
        sinon l'opérateur configuré."""
        user = request.headers.get("x-remote-user", "").strip()
        return user if self.trust_proxy_user and user else self.operator

    def role_for(self, request: Request) -> str:
        """Avec des comptes nginx, un compte sans rôle déclaré ne peut rien valider."""
        if not self.trust_proxy_user:
            return self.default_role
        return self.roles.get(self.operator_for(request), "observer")

    def gateway(self) -> OpenRouterGateway | None:
        key = self.secrets.get(OPENROUTER_KEY)
        return self.gateway_factory(key) if key else None

    def budgeted_gateway(self) -> BudgetedGateway | None:
        inner = self.gateway()
        if inner is None:
            return None
        return BudgetedGateway(inner, self.ledger, self.cap_cad, self.task_cap_cad)

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


def open_database(config: AppConfig) -> sessionmaker[Session]:
    """Mode léger (SQLite) : tables créées à la volée, ajouts seulement, jamais de suppression.
    PostgreSQL : schéma géré par les migrations Alembic."""
    if config.is_lightweight:
        Path(config.database_url.removeprefix("sqlite:///")).parent.mkdir(
            parents=True, exist_ok=True
        )
    engine = make_engine(config.database_url)
    if config.is_lightweight:
        Base.metadata.create_all(engine)
        create_audit_table(engine)
    return sessionmaker(engine, expire_on_commit=False)


def build_services(config: AppConfig) -> Services:
    sessions = open_database(config)
    catalog = load_catalog(config.catalog_path)
    pmbok = load_pmbok_skills(config.pmbok_skills_path)
    pmbok.check_agents(catalog)
    services = Services(
        catalog=catalog,
        repo=SettingsRepository(sessions, catalog, pmbok),
        ledger=SqlUsageLedger(sessions),
        secrets=KeyringSecretStore(),
        gateway_factory=lambda key: OpenRouterGateway(key, config.usd_to_cad),
        cap_cad=config.budget_cap_cad,
        task_cap_cad=config.task_cap_cad,
        operator=config.operator,
        trust_proxy_user=config.trust_proxy_user,
        roles=dict(config.roles),
        default_role=config.operator_role,
    )
    services.audit = AuditLog(sessions, services.secrets)
    gate = ActionGate(load_policy(config.autonomy_path), catalog, services.audit)
    services.projects = ProjectAssistant(
        ProjectRepository(sessions),
        gate,
        _answerer_factory(services, gate, pmbok, config.min_relevance),
        pmbok.pages_of(INTAKE_PARTS),
    )
    return services


def _answerer_factory(
    services: Services, gate: ActionGate, pmbok: PmbokSkills, min_relevance: float
) -> Callable[[], Answerer]:
    @cache
    def memory() -> RagMemory:
        from boussole.platform.memory_rag.cli import memory as local_memory  # modèle lourd

        return local_memory()

    def build() -> Answerer:
        gateway = services.budgeted_gateway()
        if gateway is None:
            raise MissingApiKeyError("Clé OpenRouter absente : saisis-la dans la page Paramètres.")
        return Answerer(
            gate, memory(), gateway, services.repo, pmbok.pages_for, min_score=min_relevance
        )

    return build
