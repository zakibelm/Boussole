"""Phase 1 : créer un projet en une conversation, l'humain décide, tableau de bord et chat.

Base SQLite en mémoire, modèle simulé, journal signé réel. Aucune donnée réelle.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from boussole.agents.answer import Answerer, MissingApiKeyError
from boussole.api.app import create_app
from boussole.api.services import Services
from boussole.core.enums import Approach, DecisionStatus
from boussole.core.models import AgentLogEntry, Base
from boussole.platform.audit.log import create_audit_table
from boussole.platform.guardrails.gate import ActionGate
from boussole.platform.llm_gateway.budget import BudgetedGateway, InMemoryLedger
from boussole.platform.memory_rag.port import Chunk
from boussole.platform.secrets import InMemorySecretStore
from boussole.projects.assistant import (
    RECOMMEND,
    DecisionRefusedError,
    ProjectAssistant,
    Signer,
    parse_approach,
)
from boussole.projects.demo import NAME, seed_demo
from boussole.projects.repository import ProjectRepository
from tests.answer_support import PMBOK, ScriptedGateway, memory_with, settings_repo
from tests.guardrails_support import CATALOG, make_audit, make_gate

TODAY = date(2026, 11, 1)
CHUNKS = [
    Chunk("a1", "Guide test", "4.2.3", "Approches hybrides", 88, 89, "Critères de choix."),
    Chunk("r1", "Guide test", "2.7", "Risque", 200, 200, "Registre des risques."),
]
REPLY = "Le lot 1 est figé, le lot 2 incertain [1].\n\nApproche recommandée : **hybride**"

Sessions = sessionmaker[Session]
ZAKI = Signer("Zakaria", "pmo")
GUEST = Signer("Invité", "observer")


@pytest.fixture
def sessions() -> Sessions:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    create_audit_table(engine)
    return sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def model() -> ScriptedGateway:
    return ScriptedGateway(REPLY)


@pytest.fixture
def gate(sessions: Sessions) -> ActionGate:
    return make_gate(make_audit(sessions))


def _assistant(sessions: Sessions, gate: ActionGate, model: ScriptedGateway) -> ProjectAssistant:
    def answerer() -> Answerer:
        gateway = BudgetedGateway(model, InMemoryLedger(), Decimal("20"))
        return Answerer(gate, memory_with(CHUNKS), gateway, settings_repo(), PMBOK.pages_for)

    return ProjectAssistant(ProjectRepository(sessions), gate, answerer)


@pytest.fixture
def assistant(sessions: Sessions, gate: ActionGate, model: ScriptedGateway) -> ProjectAssistant:
    return _assistant(sessions, gate, model)


def _log(sessions: Sessions) -> list[AgentLogEntry]:
    with sessions() as session:
        return list(session.scalars(select(AgentLogEntry).order_by(AgentLogEntry.id)))


def _proposed(assistant: ProjectAssistant) -> tuple[uuid.UUID, uuid.UUID]:
    project_id = assistant.projects.create("Portail", "Lot 1 figé, lot 2 à découvrir.")
    return project_id, assistant.propose_approach(project_id)


@pytest.mark.parametrize(
    ("text", "approach"),
    [
        ("…\nApproche recommandée : hybride", Approach.HYBRID),
        ("Approche recommandée : **Prédictive**", Approach.PREDICTIVE),
        ("approche recommandee: adaptative.", Approach.ADAPTIVE),
        ("Approche recommandée : hybride\nApproche recommandée : prédictive", Approach.PREDICTIVE),
        ("Aucune recommandation", None),
    ],
)
def test_the_recommended_approach_is_read_from_the_last_line(
    text: str, approach: Approach | None
) -> None:
    assert parse_approach(text) is approach


def test_the_selector_proposes_but_does_not_decide(
    assistant: ProjectAssistant, sessions: Sessions, model: ScriptedGateway
) -> None:
    project_id, decision_id = _proposed(assistant)
    decision = assistant.projects.decision(project_id, decision_id)
    assert decision.title == "Approche hybride" and decision.status is DecisionStatus.PROPOSED
    assert "[1] Guide test, section 4.2.3" in decision.rationale and "$ CA" in decision.rationale
    assert assistant.projects.get(project_id).approach is Approach.UNDECIDED
    proposal = _log(sessions)[-1]
    assert (proposal.action, proposal.payload["verdict"]) == (RECOMMEND, "needs_human")
    assert "<projet>" in model.requests[0].messages[1].content


def test_a_named_human_approves_the_proposal(
    assistant: ProjectAssistant, sessions: Sessions
) -> None:
    project_id, decision_id = _proposed(assistant)
    assistant.decide(project_id, decision_id, Approach.HYBRID, "", ZAKI)
    assert assistant.projects.get(project_id).approach is Approach.HYBRID
    decision = assistant.projects.decision(project_id, decision_id)
    assert (decision.status, decision.decided_by) == (DecisionStatus.APPROVED, "Zakaria")
    approval = _log(sessions)[-1].payload
    assert (approval["verdict"], approval["approver"]) == ("allow", "Zakaria")


def test_choosing_another_approach_requires_a_reason(assistant: ProjectAssistant) -> None:
    project_id, decision_id = _proposed(assistant)
    with pytest.raises(ValueError, match="raison"):
        assistant.decide(project_id, decision_id, Approach.PREDICTIVE, " ", ZAKI)
    assistant.decide(project_id, decision_id, Approach.PREDICTIVE, "Contrat à prix fixe", ZAKI)
    decision = assistant.projects.decision(project_id, decision_id)
    assert (decision.status, decision.reason) == (DecisionStatus.MODIFIED, "Contrat à prix fixe")


def test_a_role_without_authority_cannot_decide_nor_reject(assistant: ProjectAssistant) -> None:
    project_id, decision_id = _proposed(assistant)
    with pytest.raises(DecisionRefusedError):
        assistant.decide(project_id, decision_id, Approach.HYBRID, "", GUEST)
    with pytest.raises(DecisionRefusedError):
        assistant.reject(project_id, decision_id, "Pas d'accord", GUEST)
    assert assistant.projects.get(project_id).approach is Approach.UNDECIDED
    assert assistant.projects.pending_decision(project_id) is not None


def test_rejection_requires_a_reason_and_is_logged(
    assistant: ProjectAssistant, sessions: Sessions
) -> None:
    project_id, decision_id = _proposed(assistant)
    with pytest.raises(ValueError, match="raison"):
        assistant.reject(project_id, decision_id, "", ZAKI)
    assistant.reject(project_id, decision_id, "Il manque le contexte du lot 2", ZAKI)
    assert assistant.projects.decision(project_id, decision_id).status is DecisionStatus.REJECTED
    assert _log(sessions)[-1].payload["human"] == "rejected"
    with pytest.raises(ValueError, match="déjà prise"):
        assistant.reject(project_id, decision_id, "Encore", ZAKI)


def test_a_new_proposal_replaces_the_pending_one(assistant: ProjectAssistant) -> None:
    project_id, first = _proposed(assistant)
    second = assistant.propose_approach(project_id)
    assert assistant.projects.pending_decision(project_id).id == second  # type: ignore[union-attr]
    assert assistant.projects.decision(project_id, first).status is DecisionStatus.REJECTED


def test_a_decision_cannot_be_reached_from_another_project(assistant: ProjectAssistant) -> None:
    _, decision_id = _proposed(assistant)
    other = assistant.projects.create("Autre", "")
    with pytest.raises(KeyError):
        assistant.decide(other, decision_id, Approach.HYBRID, "", ZAKI)


def test_dashboard_figures_come_from_the_data(sessions: Sessions) -> None:
    project_id = seed_demo(sessions, TODAY)
    board = ProjectRepository(sessions).dashboard(project_id, TODAY)
    assert (board.deliverables_done, board.deliverables_total) == (1, 4)
    assert (board.tasks_total, board.tasks_overdue) == (8, 2)
    assert board.risks_open == 4
    assert [r.score for r in board.top_risks] == [16, 15]
    assert (board.budget_planned_cad, board.budget_actual_cad) == (Decimal(180000), Decimal(82500))
    assert board.budget_consumed_pct == 46


def test_chat_is_limited_to_the_project(
    assistant: ProjectAssistant, model: ScriptedGateway, sessions: Sessions
) -> None:
    project_id = assistant.projects.create("Portail", "Migration de 12 000 comptes.")
    answer = assistant.ask(project_id, "domain.risk", "Quels risques ?")
    assert "Migration de 12 000 comptes" in model.requests[0].messages[1].content
    assert {e.project_id for e in _log(sessions)} == {project_id}
    assert answer.audit_ids


# --- Pages web ---------------------------------------------------------------


def _services(assistant: ProjectAssistant, **extra: object) -> Services:
    return Services(
        catalog=CATALOG,
        repo=settings_repo(),
        ledger=InMemoryLedger(),
        secrets=InMemorySecretStore(),
        gateway_factory=lambda key: None,  # type: ignore[arg-type,return-value]
        cap_cad=Decimal("20"),
        operator="Zakaria",
        projects=assistant,
        **extra,  # type: ignore[arg-type]
    )


@pytest.fixture
def client(assistant: ProjectAssistant) -> TestClient:
    return TestClient(create_app(_services(assistant)))


def test_home_leads_to_projects(client: TestClient) -> None:
    assert client.get("/", follow_redirects=False).headers["location"] == "/projects"


def test_project_is_created_in_one_conversation(client: TestClient) -> None:
    response = client.post("/projects", data={"name": "Portail", "description": "Lot 1 figé."})
    assert (
        response.status_code == 200
        and "Proposition du sélecteur : Approche hybride" in response.text
    )
    assert "Valider" in response.text and "Guide test, section 4.2.3" in response.text
    assert "Portail" in client.get("/projects").text


def test_human_decision_from_the_page(client: TestClient, assistant: ProjectAssistant) -> None:
    project_id, decision_id = _proposed(assistant)
    page = client.post(
        f"/projects/{project_id}/decisions/{decision_id}",
        data={"verdict": "approve", "approach": "hybrid", "reason": ""},
    ).text
    assert "Décision enregistrée" in page and "hybride" in page


def test_dashboard_and_chat_on_the_project_page(
    client: TestClient, assistant: ProjectAssistant, sessions: Sessions
) -> None:
    project_id = seed_demo(sessions, date.today())
    page = client.get(f"/projects/{project_id}").text
    assert NAME in page and "1 / 4" in page and "82 500 sur 180 000 $ CA" in page
    answer = client.post(
        f"/projects/{project_id}/ask", data={"agent": "domain.risk", "question": "Risques ?"}
    ).text
    assert "Guide test, section 2.7" in answer and "0.0021 $ CA" in answer


def test_missing_key_is_explained_not_crashed(sessions: Sessions, gate: ActionGate) -> None:
    def no_key() -> Answerer:
        raise MissingApiKeyError("Clé OpenRouter absente.")

    assistant = ProjectAssistant(ProjectRepository(sessions), gate, no_key)
    client = TestClient(create_app(_services(assistant)))
    page = client.post("/projects", data={"name": "Sans clé", "description": ""}).text
    assert "Proposition impossible : Clé OpenRouter absente." in page


def test_agents_receive_the_project_figures(
    assistant: ProjectAssistant, model: ScriptedGateway, sessions: Sessions
) -> None:
    project_id = seed_demo(sessions, date.today())
    assistant.ask(project_id, "domain.risk", "Registre des risques et budget consommé ?")
    sent = model.requests[0].messages[1].content
    assert "Livrables terminés : 1 sur 4" in sent and "en retard : 2" in sent
    assert "82500" in sent and "(46 %)" in sent


def test_a_new_project_says_it_has_no_data(assistant: ProjectAssistant) -> None:
    project_id = assistant.projects.create("Vide", "")
    assert "Aucune donnée saisie" in assistant.context(project_id)


# --- Failles corrigées (tests du 1er novembre 2026) -------------------------


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": "https://piege.example"},
        {"Origin": "null"},
        {"Referer": "https://piege.example/page"},
        {"Sec-Fetch-Site": "cross-site", "Origin": "http://testserver"},
        {"Sec-Fetch-Site": "same-site"},
    ],
)
def test_forms_from_another_site_are_refused(
    client: TestClient, assistant: ProjectAssistant, headers: dict[str, str]
) -> None:
    project_id, decision_id = _proposed(assistant)
    response = client.post(
        f"/projects/{project_id}/decisions/{decision_id}",
        data={"verdict": "approve", "approach": "hybrid"},
        headers=headers,
    )
    assert response.status_code == 403 and "CSRF" in response.text
    assert assistant.projects.get(project_id).approach is Approach.UNDECIDED


def test_forms_from_boussole_itself_are_accepted(
    client: TestClient, assistant: ProjectAssistant
) -> None:
    project_id, decision_id = _proposed(assistant)
    client.post(
        f"/projects/{project_id}/decisions/{decision_id}",
        data={"verdict": "approve", "approach": "hybrid"},
        headers={"Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
    )
    assert assistant.projects.get(project_id).approach is Approach.HYBRID


def test_the_signer_is_the_account_authenticated_by_nginx(assistant: ProjectAssistant) -> None:
    services = _services(assistant, trust_proxy_user=True, roles={"marie": "pmo"})
    client = TestClient(create_app(services))
    project_id, decision_id = _proposed(assistant)
    url = f"/projects/{project_id}/decisions/{decision_id}"
    data = {"verdict": "approve", "approach": "hybrid"}
    refused = client.post(url, data=data, headers={"X-Remote-User": "visiteur"}).text
    assert "ne peut pas valider" in refused
    client.post(url, data=data, headers={"X-Remote-User": "marie"})
    assert assistant.projects.decision(project_id, decision_id).decided_by == "marie"


def test_errors_are_pages_not_json(client: TestClient) -> None:
    for url in ("/projects/abc", f"/projects/{uuid.uuid4()}"):
        response = client.get(url)
        assert response.status_code in (404, 422) and "<h1>" in response.text
