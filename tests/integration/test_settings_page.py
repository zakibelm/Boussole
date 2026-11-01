"""Page Paramètres de bout en bout, avec OpenRouter simulé (aucun appel payant)."""

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from markupsafe import escape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from boussole.agents.catalog import load_catalog
from boussole.api.app import create_app
from boussole.api.services import Services
from boussole.core.models import Base
from boussole.platform.llm_gateway.budget import InMemoryLedger
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from boussole.platform.secrets import OPENROUTER_KEY, InMemorySecretStore
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import SettingsRepository
from tests.contract import simulated_openrouter
from tests.guardrails_support import make_audit

CATALOG = load_catalog(Path(__file__).resolve().parents[2] / "config" / "agents.yaml")
VALID_KEY = "sk-or-test"
MODEL = "anthropic/claude-sonnet-5.5"
FREE_MODEL = "meta-llama/llama-4-scout:free"


@pytest.fixture
def services() -> Services:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    sessions = sessionmaker(engine, expire_on_commit=False)
    return Services(
        catalog=CATALOG,
        repo=SettingsRepository(sessions, CATALOG),
        ledger=InMemoryLedger(),
        secrets=InMemorySecretStore(),
        gateway_factory=lambda key: OpenRouterGateway(
            key, Decimal("1.40"), transport=simulated_openrouter.transport()
        ),
        cap_cad=Decimal("20"),
        operator="Zakaria",
        audit=make_audit(),
    )


@pytest.fixture
def client(services: Services) -> TestClient:
    return TestClient(create_app(services))


def test_page_lists_every_agent_and_sub_agent(client: TestClient) -> None:
    page = client.get("/settings").text
    for agent in CATALOG.all_agents():
        assert str(escape(agent.name)) in page
    assert "Aucune clé enregistrée" in page


def test_key_is_stored_masked_and_never_rendered(client: TestClient, services: Services) -> None:
    response = client.post("/settings/api-key", data={"api_key": "sk-or-v1-secret9876"})
    assert services.secrets.get(OPENROUTER_KEY) == "sk-or-v1-secret9876"
    assert "••••9876" in response.text
    assert "secret9876" not in client.get("/settings").text


def test_malformed_key_is_refused(client: TestClient, services: Services) -> None:
    response = client.post("/settings/api-key", data={"api_key": "hello"})
    assert "sk-or-" in response.text
    assert services.secrets.get(OPENROUTER_KEY) is None


def test_connection_test_reports_success(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    assert "Connexion réussie" in client.post("/settings/api-key/test").text


def test_connection_test_reports_invalid_key(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, "sk-or-wrong")
    assert "401" in client.post("/settings/api-key/test").text


def test_key_can_be_deleted(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    client.post("/settings/api-key/delete")
    assert services.secrets.get(OPENROUTER_KEY) is None


def test_models_come_from_openrouter_with_cad_prices(
    client: TestClient, services: Services
) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    page = client.get("/settings").text
    assert MODEL in page and "4.20 / 21.00 $ CA" in page


def test_agents_choose_from_a_menu_grouped_by_provider(
    client: TestClient, services: Services
) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    page = client.get("/settings").text
    assert 'class="model-select"' in page and "<datalist" not in page
    assert f'<optgroup label="Payants · {MODEL.split("/")[0]}">' in page


def test_free_models_come_first_in_their_own_group(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    page = client.get("/settings").text
    free, paid = page.index('<optgroup label="Gratuits'), page.index('<optgroup label="Payants')
    assert free < page.index(FREE_MODEL) < paid < page.index(MODEL, paid)


def test_model_menus_come_with_a_search_field(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    page = client.get("/settings").text
    assert "Rechercher un modèle" in page and "model-search" in page


def test_a_free_model_can_be_chosen(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    client.post("/settings/agents/domain.risk/model", data={"model": FREE_MODEL})
    assert services.repo.effective_model("domain.risk") == FREE_MODEL


def test_without_key_the_model_stays_a_text_field(client: TestClient) -> None:
    page = client.get("/settings").text
    assert 'class="model-select"' not in page and 'name="model"' in page


def test_model_choice_is_saved(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    response = client.post("/settings/agents/domain.risk/model", data={"model": MODEL})
    assert "Enregistré" in response.text
    assert services.repo.effective_model("domain.risk") == MODEL


def test_model_unknown_to_openrouter_is_refused(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    response = client.post("/settings/agents/domain.risk/model", data={"model": "x/inexistant"})
    assert "inconnu" in response.text
    assert services.repo.effective_model("domain.risk") == CATALOG.get("domain.risk").default_model


def test_unknown_agent_returns_404(client: TestClient) -> None:
    assert client.get("/settings/agents/inconnu/skill").status_code == 404


def test_skill_edit_creates_a_version(client: TestClient, services: Services) -> None:
    client.post("/settings/agents/selector/skill", data={"text": "Nouveau skill", "reason": "Test"})
    skill = services.repo.current_skill("selector")
    assert (skill.version, skill.text, skill.author) == (1, "Nouveau skill", "Zakaria")


def test_refine_proposes_without_saving(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    response = client.post(
        "/settings/agents/selector/skill/refine",
        data={"text": "Brouillon", "instruction": "Plus court"},
    )
    assert "Proposition de l'IA" in response.text
    assert services.repo.current_skill("selector").version == 0
    assert isinstance(services.ledger, InMemoryLedger)
    assert services.ledger.entries[0].agent == "skill_refiner"


def test_refine_without_key_is_explained(client: TestClient) -> None:
    response = client.post("/settings/agents/selector/skill/refine", data={"text": "Brouillon"})
    assert "clé OpenRouter" in response.text


def test_refine_is_refused_once_budget_is_spent(client: TestClient, services: Services) -> None:
    services.secrets.set(OPENROUTER_KEY, VALID_KEY)
    services.cap_cad = Decimal("0")
    response = client.post("/settings/agents/selector/skill/refine", data={"text": "Brouillon"})
    assert str(escape("Budget d'essai atteint")) in response.text


def test_accepting_a_proposal_records_its_source(client: TestClient, services: Services) -> None:
    client.post(
        "/settings/agents/selector/skill",
        data={"text": "Version IA", "source": "ai_refined", "reason": "Raffiné par l'IA"},
    )
    assert services.repo.current_skill("selector").source == "ai_refined"


def test_revert_restores_text_as_new_version(client: TestClient, services: Services) -> None:
    for text in ("v1", "v2"):
        client.post("/settings/agents/selector/skill", data={"text": text})
    client.post("/settings/agents/selector/skill/revert/1")
    skill = services.repo.current_skill("selector")
    assert (skill.version, skill.text) == (3, "v1")
    assert client.post("/settings/agents/selector/skill/revert/9").status_code == 404
