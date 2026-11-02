"""Skill du sélecteur v3 : décision du PMO du 2026-11-02 (cas ha01 et ha02).

Quand la nature du livrable est claire, le sélecteur suit le livrable même si la préférence
de l'équipe diverge; l'hybride seulement si le livrable a des parties de nature différente.
La nouvelle version se verse à l'historique et le retour arrière reste possible.
"""

import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boussole.agents.catalog import AgentSpec, load_catalog
from boussole.core.models import Base
from boussole.platform.audit.log import AuditEvent, MissingSigningKeyError
from boussole.platform.settings_store import cli
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import SettingsRepository, SkillSource

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "config" / "agents.yaml")
SELECTOR = CATALOG.get("selector")


def _flat(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture
def repo() -> SettingsRepository:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    return SettingsRepository(sessionmaker(engine, expire_on_commit=False), CATALOG)


def test_selector_skill_is_version_3_with_its_predecessor() -> None:
    assert SELECTOR.skill_version == 3
    assert SELECTOR.previous_skill is not None
    assert _flat(SELECTOR.previous_skill) != _flat(SELECTOR.skill)


@pytest.mark.parametrize(
    "rule",
    [
        "Quand la nature du livrable est claire, suis le livrable",
        "même si la préférence de l'équipe",
        "un ouvrage physique, des exigences figées ou réglementées",
        "n'est pas une raison de recommander l'hybride",
        "Recommande l'hybride seulement si le livrable lui-même a des parties de nature différente",
    ],
)
def test_selector_skill_states_the_pmo_decision(rule: str) -> None:
    assert rule in _flat(SELECTOR.skill)


def test_previous_skill_requires_a_later_version() -> None:
    spec = {"id": "x", "name": "X", "autonomy": "augmentation", "default_model": "a/b"}
    with pytest.raises(ValidationError):
        AgentSpec.model_validate({**spec, "skill": "nouveau", "previous_skill": "ancien"})


def test_adopt_default_records_previous_then_new_and_allows_rollback(
    repo: SettingsRepository,
) -> None:
    assert repo.default_pending("selector")
    created = repo.adopt_default("selector", "Zakaria")
    assert [v.version for v in created] == [1, 2]
    assert all(v.source == SkillSource.DEFAULT for v in created)
    assert created[1].reason == "Défaut du catalogue, version 3"
    assert repo.current_skill("selector").text == SELECTOR.skill.strip()

    repo.revert_skill("selector", 1, "Zakaria")
    assert repo.current_skill("selector").text == (SELECTOR.previous_skill or "").strip()


def test_adopt_default_is_idempotent(repo: SettingsRepository) -> None:
    repo.adopt_default("selector", "Zakaria")
    assert not repo.default_pending("selector")
    assert repo.adopt_default("selector", "Zakaria") == []
    assert len(repo.skill_history("selector")) == 2


def test_adopt_default_replaces_a_pmo_edit_but_keeps_it_in_history(
    repo: SettingsRepository,
) -> None:
    repo.save_skill("selector", "Version du PMO", "Zakaria", SkillSource.MANUAL, None)
    created = repo.adopt_default("selector", "Zakaria")
    assert [v.version for v in created] == [2]
    assert repo.current_skill("selector").text == SELECTOR.skill.strip()
    repo.revert_skill("selector", 1, "Zakaria")
    assert repo.current_skill("selector").text == "Version du PMO"


def test_agent_without_previous_skill_has_nothing_to_adopt(repo: SettingsRepository) -> None:
    assert not repo.default_pending("domain.risk")
    assert repo.adopt_default("domain.risk", "Zakaria") == []


class _Audit:
    def __init__(self, fail: bool = False) -> None:
        self.events: list[AuditEvent] = []
        self._fail = fail

    def append(self, event: AuditEvent) -> int:
        if self._fail:
            raise MissingSigningKeyError("Clé de signature du journal absente.")
        self.events.append(event)
        return len(self.events)


def test_cli_journals_before_adopting(repo: SettingsRepository) -> None:
    audit = _Audit()
    assert cli.adopt_default(repo, audit, "selector", "zaki") == 0
    (event,) = audit.events
    assert isinstance(event.correlation_id, uuid.UUID)
    assert event.action == "settings.skill.adopt_default"
    assert event.payload["catalog_version"] == 3
    assert repo.current_skill("selector").version == 2


@pytest.mark.parametrize("audit", [None, _Audit(fail=True)])
def test_cli_changes_nothing_without_journal(
    repo: SettingsRepository, audit: _Audit | None
) -> None:
    assert cli.adopt_default(repo, audit, "selector", "zaki") == 2
    assert repo.skill_history("selector") == []


def test_cli_does_nothing_when_already_adopted(repo: SettingsRepository) -> None:
    repo.adopt_default("selector", "zaki")
    audit = _Audit()
    assert cli.adopt_default(repo, audit, "selector", "zaki") == 0
    assert audit.events == []
