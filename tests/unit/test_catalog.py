"""Le catalogue livré couvre l'architecture et reste cohérent."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from boussole.agents.catalog import Catalog, load_catalog

CATALOG_PATH = Path(__file__).resolve().parents[2] / "config" / "agents.yaml"

EXPECTED = {
    "selector",
    "pm_predictive",
    "pm_adaptive",
    "pm_hybrid",
    "domain.scope",
    "domain.schedule",
    "domain.finance",
    "domain.stakeholders",
    "domain.resources",
    "domain.risk",
    "principle.value",
    "principle.quality",
    "principle.sustainability",
    "principle.ethics",
    "closing",
    "skill_refiner",
}


def test_catalog_covers_the_architecture() -> None:
    ids = {a.id for a in load_catalog(CATALOG_PATH).all_agents()}
    assert ids >= EXPECTED


def test_every_project_manager_has_a_team() -> None:
    catalog = load_catalog(CATALOG_PATH)
    for pm in ("pm_predictive", "pm_adaptive", "pm_hybrid"):
        assert len(catalog.get(pm).children) == 3


def test_every_agent_has_a_model_and_a_skill() -> None:
    for agent in load_catalog(CATALOG_PATH).all_agents():
        assert "/" in agent.default_model, agent.id
        assert agent.skill.strip(), agent.id


def test_duplicate_ids_are_rejected() -> None:
    agent = {"id": "selector", "name": "S", "default_model": "a/b", "skill": "x"}
    raw = {"shared_rules": "r", "groups": [{"id": "g", "name": "G", "agents": [agent, agent]}]}
    with pytest.raises(ValidationError, match="double"):
        Catalog.model_validate(raw)


def test_unknown_agent_raises() -> None:
    with pytest.raises(KeyError):
        load_catalog(CATALOG_PATH).get("inconnu")
