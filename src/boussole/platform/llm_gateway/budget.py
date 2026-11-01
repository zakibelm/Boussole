"""Plafond de dépenses : aucun appel payant au-delà du budget fixé (en CAD)."""

import json
import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
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
# Une réservation laissée par un processus arrêté cesse de compter après ce délai
RESERVATION_TTL = timedelta(minutes=10)


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


@dataclass(frozen=True)
class Reservation:
    id: str
    amount_cad: Decimal


class UsageLedger(Protocol):
    """Registre des coûts. `reserve` et `settle` sont atomiques, y compris entre processus
    pour le registre en base (même verrou que le journal d'audit)."""

    def total_spent_cad(self) -> Decimal: ...

    def record(self, entry: UsageRecord) -> None: ...

    def reserve(self, amount: Decimal, cap: Decimal, agent: str, model: str) -> Reservation:
        """Réserve `amount` si dépensé + réservé + amount <= cap; sinon BudgetExceededError."""
        ...

    def settle(self, reservation: Reservation, entry: UsageRecord | None) -> None:
        """Libère la réservation et, si l'appel a eu lieu, enregistre son coût réel."""
        ...


def fits(spent: Decimal, reserved: Decimal, amount: Decimal, cap: Decimal) -> bool:
    """Budget épuisé : tout appel est refusé, même estimé gratuit. Sinon l'estimation
    doit tenir dans le solde, appels en cours compris."""
    available = cap - spent - reserved
    return available > 0 and amount <= available


def refusal(cap: Decimal, reserved: Decimal, amount: Decimal) -> BudgetExceededError:
    return BudgetExceededError(
        f"Budget d'essai atteint ({cap} $ CA, réservé par les appels en cours : "
        f"{reserved:.4f} $ CA, estimation : {amount:.4f} $ CA) : appel refusé."
    )


class InMemoryLedger:
    """Registre en mémoire (tests, benchmark) : un verrou pour les fils du processus."""

    def __init__(self) -> None:
        self.entries: list[UsageRecord] = []
        self._reserved: dict[str, Decimal] = {}
        self._lock = threading.Lock()

    def total_spent_cad(self) -> Decimal:
        return sum((e.usage.cost_cad for e in self.entries), Decimal("0"))

    def record(self, entry: UsageRecord) -> None:
        with self._lock:
            self.entries.append(entry)

    def reserve(self, amount: Decimal, cap: Decimal, agent: str, model: str) -> Reservation:
        with self._lock:
            reserved = sum(self._reserved.values(), Decimal("0"))
            if not fits(self.total_spent_cad(), reserved, amount, cap):
                raise refusal(cap, reserved, amount)
            reservation = Reservation(uuid.uuid4().hex, amount)
            self._reserved[reservation.id] = amount
            return reservation

    def settle(self, reservation: Reservation, entry: UsageRecord | None) -> None:
        with self._lock:
            self._reserved.pop(reservation.id, None)
            if entry is not None:
                self.entries.append(entry)


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
        reservation = self._ledger.reserve(estimate, self._cap, agent, request.model)
        try:
            result = self._inner.generate(request)
        except BaseException:
            self._ledger.settle(reservation, None)
            raise
        self._settle(reservation, UsageRecord(agent, result.model, result.usage))
        return result

    def embed(self, model: str, texts: tuple[str, ...], agent: str = "unknown") -> EmbeddingResult:
        estimate = self.estimate(model, sum(len(t) for t in texts), 0)
        reservation = self._ledger.reserve(estimate, self._cap, agent, model)
        try:
            result = self._inner.embed(model, texts)
        except BaseException:
            self._ledger.settle(reservation, None)
            raise
        self._settle(reservation, UsageRecord(agent, model, result.usage))
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

    def _settle(self, reservation: Reservation, entry: UsageRecord) -> None:
        self._ledger.settle(reservation, entry)
        if self._task_cap is not None and entry.usage.cost_cad > self._task_cap:
            log.warning(
                "plafond par tâche dépassé : agent=%s modèle=%s coût=%s $ CA plafond=%s $ CA",
                entry.agent,
                entry.model,
                entry.usage.cost_cad,
                self._task_cap,
            )
