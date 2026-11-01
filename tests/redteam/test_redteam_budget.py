"""Red team du 1er novembre 2026, constat 4 : appels simultanés et plafond.

Avant : plafond 1 $ CA, 8 appels simultanés, 8 $ CA dépensés. Chaque appel réserve
maintenant son plafond par tâche avant de partir.
"""

import threading
import time
from decimal import Decimal

import pytest

from boussole.platform.llm_gateway.budget import (
    BudgetedGateway,
    BudgetExceededError,
    InMemoryLedger,
)
from boussole.platform.llm_gateway.fake import FakeGateway
from boussole.platform.llm_gateway.port import (
    GenerationRequest,
    GenerationResult,
    Message,
    Usage,
)

REQUEST = GenerationRequest("m", (Message("user", "q"),))


class SlowPaidModel(FakeGateway):
    def __init__(self, cost: str) -> None:
        super().__init__()
        self._cost = Decimal(cost)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        time.sleep(0.2)
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


@pytest.mark.parametrize("task_cap", [None, Decimal("0.25")])
def test_concurrent_calls_stay_within_the_cap(task_cap: Decimal | None) -> None:
    ledger = InMemoryLedger()
    gateway = BudgetedGateway(SlowPaidModel("0.25"), ledger, Decimal("1.00"), task_cap)
    refused = _burst(gateway, 8)
    assert ledger.total_spent_cad() <= Decimal("1.00")
    assert refused >= 4


def test_task_cap_lets_parallel_calls_share_the_budget() -> None:
    ledger = InMemoryLedger()
    gateway = BudgetedGateway(SlowPaidModel("0.10"), ledger, Decimal("1.00"), Decimal("0.25"))
    assert _burst(gateway, 4) == 0  # 4 réservations de 0,25 $ CA tiennent dans 1 $ CA
    assert ledger.total_spent_cad() == Decimal("0.40")


def test_reservation_is_released_after_a_failed_call() -> None:
    class Broken(FakeGateway):
        def generate(self, request: GenerationRequest) -> GenerationResult:
            raise RuntimeError("panne")

    ledger = InMemoryLedger()
    gateway = BudgetedGateway(Broken(), ledger, Decimal("1.00"), Decimal("1.00"))
    with pytest.raises(RuntimeError):
        gateway.generate(REQUEST)
    ok = BudgetedGateway(SlowPaidModel("0.10"), ledger, Decimal("1.00"), Decimal("1.00"))
    ok.generate(REQUEST)  # la réservation de l'appel en panne a été libérée


def test_cost_above_the_task_cap_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    gateway = BudgetedGateway(
        SlowPaidModel("0.40"), InMemoryLedger(), Decimal("5"), Decimal("0.25")
    )
    gateway.generate(REQUEST)
    assert "plafond par tâche dépassé" in caplog.text
