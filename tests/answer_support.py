"""Outils communs aux tests de réponse sourcée : modèle scripté, mémoire et paramètres."""

from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from boussole.agents.pmbok_skills import PmbokSkills, load_pmbok_skills
from boussole.core.models import Base
from boussole.platform.llm_gateway.fake import FakeGateway
from boussole.platform.llm_gateway.port import GenerationRequest, GenerationResult, Usage
from boussole.platform.memory_rag.embedders import FakeEmbedder
from boussole.platform.memory_rag.local_store import LocalVectorStore
from boussole.platform.memory_rag.memory import RagMemory
from boussole.platform.memory_rag.port import Chunk
from boussole.platform.settings_store.models import SETTINGS_TABLES
from boussole.platform.settings_store.repository import SettingsRepository
from tests.guardrails_support import CATALOG

ROOT = Path(__file__).resolve().parents[1]
PMBOK: PmbokSkills = load_pmbok_skills(ROOT / "config" / "pmbok_skills.yaml")


class ScriptedGateway(FakeGateway):
    """Répond toujours `reply` et garde chaque requête pour inspection."""

    def __init__(self, reply: str) -> None:
        super().__init__()
        self.requests: list[GenerationRequest] = []
        self.reply = reply

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        return GenerationResult(self.reply, request.model, Usage(900, 40, Decimal("0.0021")))


def memory_with(chunks: list[Chunk]) -> RagMemory:
    embedder, store = FakeEmbedder(), LocalVectorStore()
    if chunks:
        store.add(chunks, embedder.embed_documents([c.text for c in chunks]), embedder.model_name)
    return RagMemory(embedder, store)


def settings_repo() -> SettingsRepository:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    return SettingsRepository(sessionmaker(engine, expire_on_commit=False), CATALOG, PMBOK)
