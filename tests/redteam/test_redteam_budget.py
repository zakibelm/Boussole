"""Red team du 1er novembre 2026, constat 4 : coût des appels et plafonds.

Avant : plafond 1 $ CA, 8 appels simultanés, 8 $ CA dépensés. Désormais, le coût maximal
de chaque appel est estimé au prix du modèle avant l'envoi, puis réservé.
"""

import threading
import time
from decimal import Decimal

import pytest

from boussole.platform.llm_gateway.budget import (
    BudgetedGateway,
    BudgetExceededError,
    InMemoryLedger,
    TaskCapExceededError,
    UnknownModelPriceError,
    estimate_max_cost_cad,
)
from boussole.platform.llm_gateway.fake import FakeGateway
from boussole.platform.llm_gateway.port import (
    GenerationRequest,
    GenerationResult,
    Message,
    ModelInfo,
    Usage,
)

MODEL = "test/payant"
# 250 $ CA par million de jetons en sortie : 1 000 jetons max = 0,25 $ CA (prompt gratuit)
PRICE = ModelInfo(MODEL, "Payant", 8192, Decimal("0"), Decimal("250"))
REQUEST = GenerationRequest(MODEL, (Message("user", "q"),), max_tokens=1000)


class PaidModel(FakeGateway):
    """Modèle lent qui facture `cost` par appel, au prix déclaré par PRICE."""

    def __init__(self, cost: str, delay: float = 0.2) -> None:
        super().__init__()
        self.calls = 0
        self._cost = Decimal(cost)
        self._delay = delay

    def list_models(self) -> tuple[ModelInfo, ...]:
        return (PRICE,)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        self.calls += 1
        time.sleep(self._delay)
        return GenerationResult("ok", request.model, Usage(1, 1, self._cost))


def _burst(gateway: BudgetedGateway, calls: int) -> int:
    refused: list[int] = []

    def call() -> None:
        try:
            gateway.generate(REQUEST)
        except BudgetExceededError:
            refused.append(1)

    threads = [threading.Thread(target=call) for _ in range(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return len(refused)


def test_estimate_is_prompt_plus_max_tokens_at_model_price() -> None:
    info = ModelInfo("m", "m", 1, Decimal("3"), Decimal("15"))
    # 3 000 caractères = 1 000 jetons (prudent) x 3 $ + 500 jetons x 15 $, par million
    assert estimate_max_cost_cad(3000, 500, info) == Decimal("0.0105")


@pytest.mark.parametrize("task_cap", [None, Decimal("0.25")])
def test_concurrent_calls_stay_within_the_cap(task_cap: Decimal | None) -> None:
    ledger = InMemoryLedger()
    gateway = BudgetedGateway(PaidModel("0.25"), ledger, Decimal("1.00"), task_cap)
    refused = _burst(gateway, 8)
    assert ledger.total_spent_cad() <= Decimal("1.00")
    assert refused >= 4


def test_task_cap_refuses_before_sending() -> None:
    model = PaidModel("0.01")
    gateway = BudgetedGateway(model, InMemoryLedger(), Decimal("5"), Decimal("0.10"))
    with pytest.raises(TaskCapExceededError, match="avant l'envoi"):
        gateway.generate(REQUEST)  # estimation 0,25 $ CA > plafond par tâche 0,10 $ CA
    assert model.calls == 0


def test_unknown_model_price_is_refused_before_sending() -> None:
    model = PaidModel("0.01")
    gateway = BudgetedGateway(model, InMemoryLedger(), Decimal("5"), Decimal("1"))
    with pytest.raises(UnknownModelPriceError, match="Prix inconnu"):
        gateway.generate(GenerationRequest("inconnu/modele", (Message("user", "q"),)))
    assert model.calls == 0


def test_calls_within_the_task_cap_share_the_budget() -> None:
    ledger = InMemoryLedger()
    gateway = BudgetedGateway(PaidModel("0.10"), ledger, Decimal("1.00"), Decimal("0.25"))
    assert _burst(gateway, 4) == 0  # 4 réservations de 0,25 $ CA tiennent dans 1 $ CA
    assert ledger.total_spent_cad() == Decimal("0.40")


def test_reservation_is_released_after_a_failed_call() -> None:
    class Broken(PaidModel):
        def generate(self, request: GenerationRequest) -> GenerationResult:
            raise RuntimeError("panne")

    ledger = InMemoryLedger()
    with pytest.raises(RuntimeError):
        BudgetedGateway(Broken("0"), ledger, Decimal("0.25")).generate(REQUEST)
    # La réservation de l'appel en panne est libérée : tout le budget reste disponible
    BudgetedGateway(PaidModel("0.10", 0), ledger, Decimal("0.25")).generate(REQUEST)


def test_cost_above_the_estimate_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    gateway = BudgetedGateway(PaidModel("0.40", 0), InMemoryLedger(), Decimal("5"), Decimal("0.25"))
    gateway.generate(REQUEST)  # facturé 0,40 $ CA malgré une estimation de 0,25 $ CA
    assert "plafond par tâche dépassé" in caplog.text
