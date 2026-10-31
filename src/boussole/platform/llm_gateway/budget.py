"""Plafond de dépenses : aucun appel payant au-delà du budget fixé (en CAD)."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from boussole.platform.llm_gateway.port import (
    EmbeddingResult,
    GenerationRequest,
    GenerationResult,
    LLMGateway,
    ModelInfo,
    Usage,
)


class BudgetExceededError(RuntimeError):
    pass


@dataclass(frozen=True)
class UsageRecord:
    agent: str
    model: str
    usage: Usage


class UsageLedger(Protocol):
    def total_spent_cad(self) -> Decimal: ...

    def record(self, entry: UsageRecord) -> None: ...


class InMemoryLedger:
    def __init__(self) -> None:
        self.entries: list[UsageRecord] = []

    def total_spent_cad(self) -> Decimal:
        return sum((e.usage.cost_cad for e in self.entries), Decimal("0"))

    def record(self, entry: UsageRecord) -> None:
        self.entries.append(entry)


class BudgetedGateway:
    """Enveloppe une passerelle : vérifie le plafond avant, enregistre le coût après."""

    def __init__(self, inner: LLMGateway, ledger: UsageLedger, cap_cad: Decimal) -> None:
        self._inner = inner
        self._ledger = ledger
        self._cap = cap_cad

    def remaining_cad(self) -> Decimal:
        return self._cap - self._ledger.total_spent_cad()

    def generate(self, request: GenerationRequest, agent: str = "unknown") -> GenerationResult:
        self._ensure_budget()
        result = self._inner.generate(request)
        self._ledger.record(UsageRecord(agent, result.model, result.usage))
        return result

    def embed(self, model: str, texts: tuple[str, ...], agent: str = "unknown") -> EmbeddingResult:
        self._ensure_budget()
        result = self._inner.embed(model, texts)
        self._ledger.record(UsageRecord(agent, model, result.usage))
        return result

    def list_models(self) -> tuple[ModelInfo, ...]:
        return self._inner.list_models()

    def _ensure_budget(self) -> None:
        if self.remaining_cad() <= 0:
            raise BudgetExceededError(
                f"Budget d'essai atteint ({self._cap} $ CA) : appel payant refusé."
            )
