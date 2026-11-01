"""Le PMBOK en skills : affectation par agent et recherche limitée à ses pages."""

import uuid
from pathlib import Path

import pytest
from pydantic import ValidationError

from boussole.agents.catalog import load_catalog
from boussole.agents.pmbok_skills import PmbokSkills, load_pmbok_skills
from boussole.platform.memory_rag.embedders import FakeEmbedder
from boussole.platform.memory_rag.local_store import LocalVectorStore
from boussole.platform.memory_rag.port import Chunk

CONFIG = Path(__file__).resolve().parents[2] / "config"
CATALOG = load_catalog(CONFIG / "agents.yaml")
SKILLS = load_pmbok_skills(CONFIG / "pmbok_skills.yaml")

ORCHESTRATORS = ("selector", "pm_predictive", "pm_adaptive", "pm_hybrid")
DOMAINS = {
    "domain.scope": "guide.scope",
    "domain.schedule": "guide.schedule",
    "domain.finance": "guide.finance",
    "domain.stakeholders": "guide.stakeholders",
    "domain.resources": "guide.resources",
    "domain.risk": "guide.risk",
}


def _skills(agents: dict[str, object], pages: tuple[int, int] = (10, 20)) -> PmbokSkills:
    return PmbokSkills.model_validate(
        {"source": "Livre", "parts": {"p": {"label": "Partie", "pages": pages}}, "agents": agents}
    )


def test_every_mapped_agent_exists_in_the_catalog() -> None:
    SKILLS.check_agents(CATALOG)


def test_every_agent_except_tools_reads_the_book() -> None:
    expected = {a.id for a in CATALOG.all_agents()} - {"skill_refiner"}
    assert set(SKILLS.agents) == expected


@pytest.mark.parametrize("agent_id", ORCHESTRATORS)
def test_orchestrators_share_the_whole_book(agent_id: str) -> None:
    assert SKILLS.pages_for(agent_id) is None
    assert "tout le PMBOK 8" in SKILLS.note_for(agent_id)


@pytest.mark.parametrize(("agent_id", "part"), DOMAINS.items())
def test_each_domain_reads_its_own_performance_domain(agent_id: str, part: str) -> None:
    pages = SKILLS.pages_for(agent_id)
    assert pages is not None and SKILLS.parts[part].pages in pages
    assert SKILLS.parts[part].label in SKILLS.note_for(agent_id)


def test_domains_do_not_read_each_others_domain() -> None:
    for agent_id, own in DOMAINS.items():
        others = {SKILLS.parts[p].pages for p in DOMAINS.values() if p != own}
        assert others.isdisjoint(SKILLS.pages_for(agent_id) or ())


def test_agent_without_book_has_no_note_and_no_pages() -> None:
    assert SKILLS.note_for("skill_refiner") == ""
    assert SKILLS.pages_for("skill_refiner") == ()


def test_unknown_part_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Parties inconnues"):
        _skills({"selector": ["absente"]})


def test_reversed_pages_are_rejected() -> None:
    with pytest.raises(ValidationError, match="Pages invalides"):
        _skills({"selector": ["p"]}, pages=(20, 10))


def test_unknown_agent_is_rejected() -> None:
    with pytest.raises(ValueError, match="Agents inconnus"):
        _skills({"intrus": ["p"]}).check_agents(CATALOG)


def _chunk(chunk_id: str, pages: tuple[int, int], project: uuid.UUID | None = None) -> Chunk:
    return Chunk(chunk_id, "Livre", "1", "", pages[0], pages[1], "budget du projet", project)


def test_search_is_limited_to_the_agent_pages() -> None:
    store, embedder = LocalVectorStore(), FakeEmbedder()
    project = uuid.uuid4()
    chunks = [
        _chunk("avant", (1, 9)),
        _chunk("chevauche", (8, 11)),
        _chunk("dedans", (15, 15)),
        _chunk("apres", (21, 30)),
        _chunk("projet", (1, 1), project),
    ]
    store.add(chunks, embedder.embed_documents([c.text for c in chunks]), embedder.model_name)
    query = embedder.embed_query("budget")
    seen = {h.chunk.id for h in store.search(query, 10, embedder.model_name, project, ((10, 20),))}
    everything = {h.chunk.id for h in store.search(query, 10, embedder.model_name, project)}
    assert seen == {"chevauche", "dedans", "projet"}
    assert everything == {c.id for c in chunks}
