"""Le catalogue livré suit le document d'architecture et reste cohérent."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from boussole.agents.catalog import Catalog, load_catalog
from boussole.core.enums import Autonomy

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "config" / "agents.yaml")

AUTO, ASSIST, AUGMENT = Autonomy.AUTOMATION, Autonomy.ASSISTANCE, Autonomy.AUGMENTATION

# Tableau « Agents, rôles et niveaux d'autonomie » de docs/architecture/architecture.md
ARCHITECTURE = {
    "selector": AUGMENT,
    "pm_predictive": AUGMENT,
    "pm_adaptive": AUGMENT,
    "pm_hybrid": AUGMENT,
    "pm_predictive.planner": ASSIST,
    "pm_predictive.milestones": AUTO,
    "pm_adaptive.scrum_master": ASSIST,
    "pm_adaptive.product_owner": AUGMENT,
    "pm_hybrid.coordinator": ASSIST,
    "pm_hybrid.kpi_tracking": AUTO,
    "domain.scope": ASSIST,
    "domain.schedule": ASSIST,
    "domain.finance": ASSIST,
    "domain.risk": ASSIST,
    "domain.stakeholders": AUGMENT,
    "domain.resources": AUTO,
    "closing": AUTO,
}

TEAMS = {
    "pm_predictive": {"pm_predictive.planner", "pm_predictive.milestones"},
    "pm_adaptive": {"pm_adaptive.scrum_master", "pm_adaptive.product_owner"},
    "pm_hybrid": {"pm_hybrid.coordinator", "pm_hybrid.kpi_tracking"},
}


@pytest.mark.parametrize(("agent_id", "level"), sorted(ARCHITECTURE.items()))
def test_autonomy_matches_the_architecture(agent_id: str, level: Autonomy) -> None:
    assert CATALOG.get(agent_id).autonomy == level


@pytest.mark.parametrize(("pm", "team"), sorted(TEAMS.items()))
def test_project_manager_teams_match_the_architecture(pm: str, team: set[str]) -> None:
    assert {child.id for child in CATALOG.get(pm).children} == team


def test_principles_are_present() -> None:
    for name in ("value", "quality", "sustainability", "ethics"):
        CATALOG.get(f"principle.{name}")


def test_every_agent_has_a_model_and_a_skill() -> None:
    for agent in CATALOG.all_agents():
        assert "/" in agent.default_model, agent.id
        assert agent.skill.strip(), agent.id


def test_duplicate_ids_are_rejected() -> None:
    agent = {
        "id": "selector",
        "name": "S",
        "autonomy": "assistance",
        "default_model": "a/b",
        "skill": "x",
    }
    raw = {"shared_rules": "r", "groups": [{"id": "g", "name": "G", "agents": [agent, agent]}]}
    with pytest.raises(ValidationError, match="double"):
        Catalog.model_validate(raw)


def test_unknown_agent_raises() -> None:
    with pytest.raises(KeyError):
        CATALOG.get("inconnu")
