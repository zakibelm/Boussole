"""Réservations de budget sous PostgreSQL : deux workers, un seul plafond (migration 0004)."""

import pytest
from sqlalchemy import Engine, text

from tests.redteam.test_redteam_budget_db import CAP, burst_on_two_workers

pytestmark = pytest.mark.integration


def test_two_workers_share_the_cap_under_postgresql(engine: Engine, database_url: str) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM llm_reservations"))
        conn.execute(text("DELETE FROM llm_usage"))
    spent, refused = burst_on_two_workers(database_url)
    assert spent <= CAP
    assert refused >= 4
