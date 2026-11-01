"""Critère de sortie de la phase 0 : une réponse sourcée et journalisée de bout en bout.

Extraits fabriqués pour le test (aucun texte du PMBOK), modèle simulé, journal signé réel.
"""

import json
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from boussole.agents.answer import ANSWER, ANSWER_RULES, SEARCH, Answerer, AnswerRefusedError
from boussole.agents.answer_cli import render
from boussole.agents.pmbok_skills import load_pmbok_skills
from boussole.core.models import AgentLogEntry, Base
from boussole.platform.audit.log import AuditLog
from boussole.platform.llm_gateway.budget import (
    BudgetedGateway,
    BudgetExceededError,
    InMemoryLedger,
)
from boussole.platform.llm_gateway.fake import FakeGateway
from boussole.platform.llm_gateway.openrouter import _chat_body
from boussole.platform.llm_gateway.port import GenerationRequest, GenerationResult, Usage
from boussole.platform.memory_rag.embedders import FakeEmbedder
from boussole.platform.memory_rag.local_store import LocalVectorStore
from boussole.platform.memory_rag.memory import NO_SOURCE, RagMemory
from boussole.platform.memory_rag.port import Chunk
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import SettingsRepository
from tests.guardrails_support import CATALOG, audit_sessions, make_audit, make_gate

ROOT = Path(__file__).resolve().parents[2]
PMBOK = load_pmbok_skills(ROOT / "config" / "pmbok_skills.yaml")
PROTECTED_EXCERPT = "Le registre consigne la probabilité et l'impact de chaque menace identifiée."
CHUNKS = [
    Chunk("c1", "Guide test", "2.7", "Risque", 200, 201, PROTECTED_EXCERPT),
    Chunk(
        "c2", "Guide test", "2.3", "Échéancier", 155, 155, "Le calendrier ordonne les activités."
    ),
]
REPLY = "Il note la probabilité et l'impact de chaque menace [1]."


class ScriptedGateway(FakeGateway):
    """Répond toujours `REPLY` et garde la dernière requête pour inspection."""

    def __init__(self) -> None:
        super().__init__()
        self.requests: list[GenerationRequest] = []
        self.reply = REPLY

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        return GenerationResult(self.reply, request.model, Usage(900, 40, Decimal("0.0021")))


def _memory(chunks: list[Chunk]) -> RagMemory:
    embedder, store = FakeEmbedder(), LocalVectorStore()
    if chunks:
        store.add(chunks, embedder.embed_documents([c.text for c in chunks]), embedder.model_name)
    return RagMemory(embedder, store)


def _repo() -> SettingsRepository:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    return SettingsRepository(sessionmaker(engine, expire_on_commit=False), CATALOG, PMBOK)


Sessions = sessionmaker[Session]


@pytest.fixture
def sessions() -> Sessions:
    return audit_sessions()


@pytest.fixture
def audit(sessions: Sessions) -> AuditLog:
    return make_audit(sessions)


@pytest.fixture
def model() -> ScriptedGateway:
    return ScriptedGateway()


def _answerer(
    audit: AuditLog, model: ScriptedGateway, chunks: list[Chunk] = CHUNKS, cap: str = "20"
) -> Answerer:
    return Answerer(
        gate=make_gate(audit),
        memory=_memory(chunks),
        gateway=BudgetedGateway(model, InMemoryLedger(), Decimal(cap)),
        repo=_repo(),
        pages_for=PMBOK.pages_for,
    )


def _log(sessions: Sessions) -> list[AgentLogEntry]:
    with sessions() as session:
        return list(session.scalars(select(AgentLogEntry).order_by(AgentLogEntry.id)))


def test_answer_is_sourced_and_logged_end_to_end(
    audit: AuditLog, sessions: Sessions, model: ScriptedGateway
) -> None:
    answer = _answerer(audit, model).answer("domain.risk", "Que contient le registre des risques ?")
    assert answer.text == REPLY and answer.cited == (1,)
    assert answer.citations == ("Guide test, section 2.7 « Risque », p. 200-201",)
    assert answer.cost_cad == Decimal("0.0021")
    entries = _log(sessions)
    assert [e.action for e in entries] == [SEARCH, ANSWER, ANSWER]
    assert {e.correlation_id for e in entries} == {answer.correlation_id}
    assert answer.audit_ids == tuple(e.id for e in entries)
    outcome = entries[-1].payload
    assert outcome["citations"] == list(answer.citations) and outcome["cited"] == [1]
    assert outcome["cost_cad"] == "0.0021" and outcome["answer_chars"] == len(REPLY)
    assert audit.verify().ok


def test_the_journal_never_holds_protected_text(
    audit: AuditLog, sessions: Sessions, model: ScriptedGateway
) -> None:
    _answerer(audit, model).answer("domain.risk", "Que contient le registre des risques ?")
    logged = json.dumps([e.payload for e in _log(sessions)], ensure_ascii=False)
    assert PROTECTED_EXCERPT not in logged and REPLY not in logged


def test_agent_only_sees_its_part_of_the_book(audit: AuditLog, model: ScriptedGateway) -> None:
    answer = _answerer(audit, model).answer("domain.risk", "Comment ordonner les activités ?")
    assert all("Échéancier" not in c for c in answer.citations)


def test_excerpts_go_only_to_providers_without_retention(
    audit: AuditLog, model: ScriptedGateway
) -> None:
    _answerer(audit, model).answer("domain.risk", "Que contient le registre des risques ?")
    request = model.requests[0]
    assert request.private and ANSWER_RULES in request.messages[0].content
    assert PROTECTED_EXCERPT in request.messages[1].content
    assert _chat_body(request)["provider"] == {"data_collection": "deny", "zdr": True}
    assert "provider" not in _chat_body(replace(request, private=False))


def test_without_source_the_model_is_not_called(
    audit: AuditLog, sessions: Sessions, model: ScriptedGateway
) -> None:
    answer = _answerer(audit, model, chunks=[]).answer("domain.risk", "Une question")
    assert answer.text == NO_SOURCE and not model.requests
    assert [e.action for e in _log(sessions)] == [SEARCH, ANSWER]


def test_spent_budget_refuses_and_logs_the_failure(
    audit: AuditLog, sessions: Sessions, model: ScriptedGateway
) -> None:
    with pytest.raises(BudgetExceededError):
        _answerer(audit, model, cap="0").answer("domain.risk", "Que contient le registre ?")
    assert _log(sessions)[-1].payload["verdict"] == "failed" and not model.requests


def test_unknown_agent_is_refused(audit: AuditLog, model: ScriptedGateway) -> None:
    with pytest.raises(AnswerRefusedError):
        _answerer(audit, model).answer("inconnu", "Une question")


def test_render_shows_sources_cost_and_journal(audit: AuditLog, model: ScriptedGateway) -> None:
    text = render(_answerer(audit, model).answer("domain.risk", "Que contient le registre ?"))
    assert "[1] Guide test, section 2.7" in text and "0.0021 $ CA" in text
    assert "Sources citées : [1]" in text and "Journal : entrées 1, 2, 3" in text


@pytest.mark.parametrize(
    ("reply", "cited"),
    [
        ("Probabilité et impact [1].", (1,)),
        ("Voir [1 — section 2.7, p. 200; 2 — section 2.3, p. 155].", (1,)),
        ("Selon [1, 2], puis la section 4.2.3 [3].", (1,)),
        ("Aucune référence ici, section 4.2.3.", ()),
    ],
)
def test_citations_are_detected_in_every_format(
    audit: AuditLog, model: ScriptedGateway, reply: str, cited: tuple[int, ...]
) -> None:
    model.reply = reply
    assert (
        _answerer(audit, model).answer("domain.risk", "Que contient le registre ?").cited == cited
    )
