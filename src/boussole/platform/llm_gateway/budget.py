"""Plafond de dépenses : aucun appel payant au-delà du budget fixé (en CAD)."""

import json
import logging
import threading
from collections.abc import Callable, Iterator
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


class TaskCapExceededError(BudgetExceededError):
    """Le coût maximal estimé d'un appel dépasse le plafond par tâche."""


class UnknownModelPriceError(BudgetExceededError):
    """Sans prix connu, le coût maximal d'un appel ne peut pas être borné."""


# Prudent : surestime le nombre de jetons (environ 4 caractères par jeton en moyenne)
CHARS_PER_TOKEN_ESTIMATE = 3
_MILLION = Decimal(1_000_000)


def estimate_max_cost_cad(prompt_chars: int, max_tokens: int, model: ModelInfo) -> Decimal:
    """Coût maximal d'un appel : (jetons du prompt + max_tokens) au prix du modèle, en $ CA."""
    prompt_tokens = -(-prompt_chars // CHARS_PER_TOKEN_ESTIMATE)
    return (
        prompt_tokens * model.prompt_cad_per_mtok + max_tokens * model.completion_cad_per_mtok
    ) / _MILLION


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
    """Enveloppe une passerelle : estime, réserve, appelle, puis enregistre le coût réel.

    Avant l'envoi, le coût maximal de l'appel est estimé au prix du modèle. L'appel est
    refusé si le prix est inconnu, si l'estimation dépasse le plafond par tâche, ou si
    « dépensé + réservé par les appels en cours + estimation » dépasse le budget.
    """

    def __init__(
        self,
        inner: LLMGateway,
        ledger: UsageLedger,
        cap_cad: Decimal,
        task_cap_cad: Decimal | None = None,
        prices: Callable[[], tuple[ModelInfo, ...]] | None = None,
    ) -> None:
        self._inner = inner
        self._ledger = ledger
        self._cap = cap_cad
        self._task_cap = task_cap_cad
        self._prices = prices
        self._price_cache: dict[str, ModelInfo] | None = None

    def remaining_cad(self) -> Decimal:
        return self._cap - self._ledger.total_spent_cad()

    def generate(self, request: GenerationRequest, agent: str = "unknown") -> GenerationResult:
        prompt_chars = sum(len(m.content) for m in request.messages)
        prompt_chars += sum(
            len(json.dumps(t.parameters)) + len(t.description) for t in request.tools
        )
        estimate = self.estimate(request.model, prompt_chars, request.max_tokens)
        with self._reservation(estimate):
            result = self._inner.generate(request)
            self._record(UsageRecord(agent, result.model, result.usage))
        return result

    def embed(self, model: str, texts: tuple[str, ...], agent: str = "unknown") -> EmbeddingResult:
        estimate = self.estimate(model, sum(len(t) for t in texts), 0)
        with self._reservation(estimate):
            result = self._inner.embed(model, texts)
            self._record(UsageRecord(agent, model, result.usage))
        return result

    def list_models(self) -> tuple[ModelInfo, ...]:
        return self._inner.list_models()

    def estimate(self, model: str, prompt_chars: int, max_tokens: int) -> Decimal:
        """Coût maximal estimé, refusé avant l'envoi s'il n'est pas borné ou trop élevé."""
        info = self._price(model)
        if info is None:
            raise UnknownModelPriceError(f"Prix inconnu pour « {model} » : appel payant refusé.")
        estimate = estimate_max_cost_cad(prompt_chars, max_tokens, info)
        if self._task_cap is not None and estimate > self._task_cap:
            raise TaskCapExceededError(
                f"Coût maximal estimé {estimate:.4f} $ CA, au-delà du plafond par tâche "
                f"({self._task_cap} $ CA) : appel refusé avant l'envoi."
            )
        return estimate

    def _price(self, model: str) -> ModelInfo | None:
        if self._price_cache is None:
            source = self._prices or self._inner.list_models
            self._price_cache = {m.id: m for m in source()}
        return self._price_cache.get(model)

    @contextmanager
    def _reservation(self, amount: Decimal) -> Iterator[None]:
        key = id(self._ledger)
        with _RESERVATION_LOCK:
            others = _RESERVED.get(key, Decimal("0"))
            available = self.remaining_cad() - others
            if available <= 0 or amount > available:
                raise BudgetExceededError(
                    f"Budget d'essai atteint ({self._cap} $ CA, réservé par les appels en "
                    f"cours : {others} $ CA, estimation : {amount:.4f} $ CA) : appel refusé."
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
