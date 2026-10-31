"""Paramètres d'agents, skills versionnés et registre des coûts LLM.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)

_SKILL_APPEND_ONLY = """
CREATE FUNCTION skill_versions_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'skill_versions est en ajout seul : % refusé', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER skill_versions_no_update_delete
    BEFORE UPDATE OR DELETE ON skill_versions
    FOR EACH ROW EXECUTE FUNCTION skill_versions_append_only();
"""


def upgrade() -> None:
    op.create_table(
        "agent_settings",
        sa.Column("agent_id", sa.String(80), primary_key=True),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("updated_by", sa.String(120), nullable=False),
        sa.Column("updated_at", _TS, server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "skill_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("agent_id", sa.String(80), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("author", sa.String(120), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_id", "version", name="uq_skill_versions_agent_version"),
    )
    op.execute(_SKILL_APPEND_ONLY)
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("agent", sa.String(80), nullable=False, index=True),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_cad", sa.Numeric(12, 6), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("llm_usage")
    op.execute("DROP TRIGGER IF EXISTS skill_versions_no_update_delete ON skill_versions")
    op.execute("DROP FUNCTION IF EXISTS skill_versions_append_only()")
    op.drop_table("skill_versions")
    op.drop_table("agent_settings")
