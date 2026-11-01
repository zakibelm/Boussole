"""Réservations de budget en base : le plafond tient entre processus (revue de l'audit, 2).

Deux registres de coûts, chacun avec son propre moteur, jouent deux workers. Huit appels
simultanés à 0,25 $ CA, plafond 1 $ CA : au plus 1,00 $ CA dépensé, et des refus.
"""

import threading
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from sqlalchemy import Engine, text
from sqlalchemy.orm import sessionmaker

from boussole.core.database import make_engine
from boussole.core.models import Base
from boussole.platform.llm_gateway.budget import BudgetedGateway, BudgetExceededError
from boussole.platform.llm_gateway.fake import FakeGateway
from boussole.platform.llm_gateway.port import (
    GenerationRequest,
    GenerationResult,
    Message,
    ModelInfo,
    Usage,
)
from boussole.platform.settings_store.models import SETTINGS_TABLES, LlmReservation
from boussole.platform.settings_store.repository import SqlUsageLedger

MODEL = "test/payant"
PRICE = ModelInfo(MODEL, "Payant", 8192, Decimal("0"), Decimal("250"))  # 0,25 $ CA / appel
REQUEST = GenerationRequest(MODEL, (Message("user", "q"),), max_tokens=1000)
CAP = Decimal("1.00")


class SlowPaidModel(FakeGateway):
    def list_models(self) -> tuple[ModelInfo, ...]:
        return (PRICE,)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        time.sleep(0.2)
        return GenerationResult("ok", request.model, Usage(1, 1, Decimal("0.25")))


def burst_on_two_workers(url: str) -> tuple[Decimal, int]:
    """8 appels simultanés, alternés entre deux registres (deux moteurs distincts)."""
    ledgers = [SqlUsageLedger(sessionmaker(make_engine(url))) for _ in range(2)]
    refused: list[int] = []

    def call(ledger: SqlUsageLedger) -> None:
        try:
            BudgetedGateway(SlowPaidModel(), ledger, CAP).generate(REQUEST)
        except BudgetExceededError:
            refused.append(1)

    threads = [threading.Thread(target=call, args=(ledgers[i % 2],)) for i in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return ledgers[0].total_spent_cad(), len(refused)


def _sqlite(tmp_path: Path) -> str:
    url = f"sqlite:///{(tmp_path / 'boussole.db').as_posix()}"
    engine: Engine = make_engine(url)
    Base.metadata.create_all(engine, tables=list(SETTINGS_TABLES))
    engine.dispose()
    return url


def test_two_workers_share_the_cap_under_sqlite(tmp_path: Path) -> None:
    spent, refused = burst_on_two_workers(_sqlite(tmp_path))
    assert spent <= CAP
    assert refused >= 4


def test_abandoned_reservation_expires(tmp_path: Path) -> None:
    url = _sqlite(tmp_path)
    sessions = sessionmaker(make_engine(url))
    now = datetime.now(UTC)
    with sessions.begin() as session:  # processus arrêté en plein appel, il y a 11 minutes
        session.add(
            LlmReservation(
                id="orpheline",
                created_at=now - timedelta(minutes=11),
                expires_at=now - timedelta(minutes=1),
                agent="selector",
                model=MODEL,
                amount_cad=CAP,
            )
        )
    gateway = BudgetedGateway(SlowPaidModel(), SqlUsageLedger(sessions), CAP)
    gateway.generate(REQUEST)  # la réservation expirée ne bloque plus le budget
    with sessions() as session:
        assert session.scalar(text("SELECT count(*) FROM llm_reservations")) == 0


def test_live_reservation_blocks_the_budget(tmp_path: Path) -> None:
    url = _sqlite(tmp_path)
    sessions = sessionmaker(make_engine(url))
    ledger = SqlUsageLedger(sessions)
    ledger.reserve(Decimal("0.90"), CAP, "selector", MODEL)  # appel en cours ailleurs
    try:
        BudgetedGateway(SlowPaidModel(), ledger, CAP).generate(REQUEST)
    except BudgetExceededError as exc:
        assert "réservé par les appels en cours" in str(exc)
    else:
        raise AssertionError("0,90 $ CA réservés + 0,25 $ CA estimés dépassent 1 $ CA")
