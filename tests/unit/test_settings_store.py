"""Paramètres d'agents sur une base SQLite en mémoire (tables génériques)."""

from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from boussole.agents.catalog import load_catalog
from boussole.core.models import Base
from boussole.platform.llm_gateway.budget import UsageRecord
from boussole.platform.llm_gateway.port import Usage
from boussole.platform.secrets import InMemorySecretStore, mask
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import (
    SettingsRepository,
    SkillSource,
    SqlUsageLedger,
)

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "config" / "agents.yaml")


@pytest.fixture
def sessions() -> sessionmaker[Session]:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def repo(sessions: sessionmaker[Session]) -> SettingsRepository:
    return SettingsRepository(sessions, CATALOG)


def test_model_defaults_to_catalog_then_follows_human_choice(repo: SettingsRepository) -> None:
    assert repo.effective_model("selector") == CATALOG.get("selector").default_model
    repo.set_model("selector", "openai/gpt-5.5", author="Zakaria")
    repo.set_model("selector", "google/gemini-3.8-flash", author="Zakaria")
    assert repo.effective_model("selector") == "google/gemini-3.8-flash"


def test_unknown_agent_is_rejected(repo: SettingsRepository) -> None:
    with pytest.raises(KeyError):
        repo.set_model("inconnu", "a/b", author="Zakaria")


def test_skill_starts_from_catalog_default(repo: SettingsRepository) -> None:
    skill = repo.current_skill("domain.risk")
    assert skill.version == 0
    assert skill.source == SkillSource.DEFAULT


def test_each_edit_creates_a_new_version(repo: SettingsRepository) -> None:
    repo.save_skill("domain.risk", "v1", "Zakaria", SkillSource.MANUAL, None)
    repo.save_skill("domain.risk", "v2", "Zakaria", SkillSource.AI_REFINED, "Plus précis")
    history = repo.skill_history("domain.risk")
    assert [s.version for s in history] == [2, 1]
    assert repo.current_skill("domain.risk").text == "v2"


def test_revert_appends_instead_of_rewriting(repo: SettingsRepository) -> None:
    repo.save_skill("domain.risk", "v1", "Zakaria", SkillSource.MANUAL, None)
    repo.save_skill("domain.risk", "v2", "Zakaria", SkillSource.MANUAL, None)
    reverted = repo.revert_skill("domain.risk", 1, "Zakaria")
    assert (reverted.version, reverted.text, reverted.source) == (3, "v1", SkillSource.REVERT)
    assert len(repo.skill_history("domain.risk")) == 3


def test_empty_skill_is_refused(repo: SettingsRepository) -> None:
    with pytest.raises(ValueError, match="vide"):
        repo.save_skill("domain.risk", "   ", "Zakaria", SkillSource.MANUAL, None)


def test_revert_to_unknown_version_raises(repo: SettingsRepository) -> None:
    with pytest.raises(KeyError):
        repo.revert_skill("domain.risk", 9, "Zakaria")


def test_system_prompt_combines_shared_rules_and_skill(repo: SettingsRepository) -> None:
    repo.save_skill("selector", "Mon skill", "Zakaria", SkillSource.MANUAL, None)
    prompt = repo.system_prompt("selector")
    assert prompt.startswith(CATALOG.shared_rules.strip())
    assert prompt.endswith("Mon skill")


def test_usage_ledger_sums_costs(sessions: sessionmaker[Session]) -> None:
    ledger = SqlUsageLedger(sessions)
    assert ledger.total_spent_cad() == 0
    for cost in ("0.25", "0.50"):
        ledger.record(UsageRecord("selector", "a/b", Usage(1, 1, Decimal(cost))))
    assert ledger.total_spent_cad() == Decimal("0.75")


def test_secrets_are_masked() -> None:
    store = InMemorySecretStore()
    store.set("k", "sk-or-v1-abcdef1234")
    assert mask(store.get("k")) == "••••1234"
    store.delete("k")
    assert mask(store.get("k")) is None
