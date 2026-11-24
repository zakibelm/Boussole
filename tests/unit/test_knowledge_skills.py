"""Connaissances métier : les 18 skills PMBOK combinés et donnés aux bons agents."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from boussole.agents.catalog import load_catalog
from boussole.agents.knowledge_skills import (
    MAX_SKILLS_PER_AGENT,
    KnowledgeSkills,
    load_knowledge_skills,
)
from boussole.core.models import Base
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import SettingsRepository

CONFIG = Path(__file__).resolve().parents[2] / "config"
CATALOG = load_catalog(CONFIG / "agents.yaml")
KNOWLEDGE = load_knowledge_skills(CONFIG / "knowledge")
MAX_NOTE_CHARS = 16_000


def test_every_mapped_agent_exists_in_the_catalog() -> None:
    KNOWLEDGE.check_agents(CATALOG)


def test_every_agent_except_tools_receives_skills() -> None:
    expected = {a.id for a in CATALOG.all_agents()} - {"skill_refiner"}
    assert set(KNOWLEDGE.agents) == expected


def test_every_skill_serves_at_least_one_agent() -> None:
    used = {name for names in KNOWLEDGE.agents.values() for name in names}
    assert used == set(KNOWLEDGE.texts)
    assert len(KNOWLEDGE.texts) == 18


@pytest.mark.parametrize("agent_id", sorted(KNOWLEDGE.agents))
def test_each_agent_gets_a_bounded_note(agent_id: str) -> None:
    assert len(KNOWLEDGE.agents[agent_id]) <= MAX_SKILLS_PER_AGENT
    note = KNOWLEDGE.note_for(agent_id)
    assert note.startswith("Connaissances métier")
    assert len(note) <= MAX_NOTE_CHARS


def test_front_matter_is_stripped_and_tool_agent_gets_nothing() -> None:
    assert all(not text.startswith("---") for text in KNOWLEDGE.texts.values())
    assert KNOWLEDGE.note_for("skill_refiner") == ""


def test_the_right_skills_reach_the_right_agents() -> None:
    assert "pmbok-finance" in KNOWLEDGE.agents["domain.finance"]
    assert "pmbok-risque-incertitude" in KNOWLEDGE.agents["domain.risk"]
    assert "pmbok-extension-logicielle" in KNOWLEDGE.agents["pm_adaptive"]
    assert "pmbok-6e-processus-49" in KNOWLEDGE.agents["pm_predictive"]


def test_unknown_skill_or_too_many_skills_are_rejected() -> None:
    texts = {name: "x" for name in "abcd"}
    with pytest.raises(ValidationError, match="inconnus"):
        KnowledgeSkills(texts=texts, agents={"selector": ["zzz"]})
    with pytest.raises(ValidationError, match="au plus"):
        KnowledgeSkills(texts=texts, agents={"selector": list("abcd")})


def test_unknown_agent_is_rejected() -> None:
    skills = KnowledgeSkills(texts={"a": "x"}, agents={"ghost": ["a"]})
    with pytest.raises(ValueError, match="ghost"):
        skills.check_agents(CATALOG)


def test_system_prompt_contains_the_knowledge_of_the_agent() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    repo = SettingsRepository(
        sessionmaker(engine, expire_on_commit=False), CATALOG, knowledge=KNOWLEDGE
    )
    prompt = repo.system_prompt("domain.finance")
    assert "### pmbok-finance" in prompt
    assert "### pmbok-risque-incertitude" not in prompt
    assert "### " not in SettingsRepository(
        sessionmaker(engine, expire_on_commit=False), CATALOG
    ).system_prompt("domain.finance")
