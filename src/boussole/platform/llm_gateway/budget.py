"""Plafond de dépenses : aucun appel payant au-delà du budget fixé (en CAD)."""

import logging
import threading
from collections.abc import Iterator
from contextlib import contextmanager
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

log = logging.getLogger(__name__)


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


# Réservations en cours, par registre de coûts : partagées par toutes les passerelles
# du processus, pour que des appels simultanés ne dépassent pas le plafond ensemble.
_RESERVED: dict[int, Decimal] = {}
_RESERVATION_LOCK = threading.Lock()


class BudgetedGateway:
    """Enveloppe une passerelle : réserve avant l'appel, enregistre le coût réel après.

    Avec un plafond par tâche, chaque appel réserve ce plafond et n'est accepté que si
    « dépensé + réservé par les autres appels + plafond par tâche » tient dans le budget.
    Sans plafond par tâche, un appel réserve tout le solde : les appels se suivent.
    """

    def __init__(
        self,
        inner: LLMGateway,
        ledger: UsageLedger,
        cap_cad: Decimal,
        task_cap_cad: Decimal | None = None,
    ) -> None:
        self._inner = inner
        self._ledger = ledger
        self._cap = cap_cad
        self._task_cap = task_cap_cad

    def remaining_cad(self) -> Decimal:
        return self._cap - self._ledger.total_spent_cad()

    def generate(self, request: GenerationRequest, agent: str = "unknown") -> GenerationResult:
        with self._reservation():
            result = self._inner.generate(request)
            self._record(UsageRecord(agent, result.model, result.usage))
        return result

    def embed(self, model: str, texts: tuple[str, ...], agent: str = "unknown") -> EmbeddingResult:
        with self._reservation():
            result = self._inner.embed(model, texts)
            self._record(UsageRecord(agent, model, result.usage))
        return result

    def list_models(self) -> tuple[ModelInfo, ...]:
        return self._inner.list_models()

    @contextmanager
    def _reservation(self) -> Iterator[None]:
        key = id(self._ledger)
        with _RESERVATION_LOCK:
            others = _RESERVED.get(key, Decimal("0"))
            available = self.remaining_cad() - others
            amount = self._task_cap if self._task_cap is not None else available
            if available <= 0 or amount <= 0 or amount > available:
                raise BudgetExceededError(
                    f"Budget d'essai atteint ({self._cap} $ CA, réservé par les appels en "
                    f"cours : {others} $ CA) : appel payant refusé."
                )
            _RESERVED[key] = others + amount
        try:
            yield
        finally:
            with _RESERVATION_LOCK:
                _RESERVED[key] -= amount

    def _record(self, entry: UsageRecord) -> None:
        self._ledger.record(entry)
        if self._task_cap is not None and entry.usage.cost_cad > self._task_cap:
            log.warning(
                "plafond par tâche dépassé : agent=%s modèle=%s coût=%s $ CA plafond=%s $ CA",
                entry.agent,
                entry.model,
                entry.usage.cost_cad,
                self._task_cap,
            )
