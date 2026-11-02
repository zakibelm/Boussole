"""Réservations de budget en base, partagées par tous les processus (revue de l'audit).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_reservations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("agent", sa.String(80), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("amount_cad", sa.Numeric(12, 6), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_reservations")
