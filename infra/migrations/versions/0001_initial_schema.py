"""Schéma initial : portefeuille, projet, livrable, tâche, risque, budget,
partie prenante, ressource, décision, journal d'agent, document de connaissance.

Revision ID: 0001
Revises:
Create Date: 2026-10-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TS = sa.DateTime(timezone=True)

_APPEND_ONLY_TRIGGER = """
CREATE FUNCTION agent_log_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'agent_log est en ajout seul : % refusé', TG_OP
        USING ERRCODE = 'insufficient_privilege';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER agent_log_no_update_delete
    BEFORE UPDATE OR DELETE ON agent_log
    FOR EACH ROW EXECUTE FUNCTION agent_log_append_only();

CREATE TRIGGER agent_log_no_truncate
    BEFORE TRUNCATE ON agent_log
    FOR EACH STATEMENT EXECUTE FUNCTION agent_log_append_only();
"""


def _base_columns() -> list[sa.Column[object]]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
    ]


def _project_fk(nullable: bool = False) -> sa.Column[object]:
    return sa.Column(
        "project_id",
        sa.Uuid(),
        sa.ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=nullable,
        index=True,
    )


def _create_projects() -> None:
    op.create_table(
        "portfolios", *_base_columns(), sa.Column("name", sa.String(200), nullable=False)
    )
    op.create_table(
        "projects",
        *_base_columns(),
        sa.Column(
            "portfolio_id",
            sa.Uuid(),
            sa.ForeignKey("portfolios.id", ondelete="SET NULL"),
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("approach", sa.String(10), nullable=False),
    )


def _create_work_items() -> None:
    op.create_table(
        "deliverables",
        *_base_columns(),
        _project_fk(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(11), nullable=False),
        sa.Column("due_date", sa.Date()),
    )
    op.create_table(
        "resources",
        *_base_columns(),
        _project_fk(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(9), nullable=False),
        sa.Column("capacity_hours", sa.Numeric(8, 2)),
    )
    op.create_table(
        "tasks",
        *_base_columns(),
        _project_fk(),
        sa.Column(
            "deliverable_id", sa.Uuid(), sa.ForeignKey("deliverables.id", ondelete="SET NULL")
        ),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("resources.id", ondelete="SET NULL")),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("status", sa.String(11), nullable=False),
        sa.Column("due_date", sa.Date()),
    )


def _create_people_and_risks() -> None:
    op.create_table(
        "stakeholders",
        *_base_columns(),
        _project_fk(),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("role", sa.String(120), nullable=False),
        sa.Column("influence", sa.Integer(), nullable=False),
        sa.Column("interest", sa.Integer(), nullable=False),
        sa.Column("consent_given_at", _TS),
        sa.CheckConstraint("influence BETWEEN 1 AND 5", name="influence_range"),
        sa.CheckConstraint("interest BETWEEN 1 AND 5", name="interest_range"),
    )
    op.create_table(
        "risks",
        *_base_columns(),
        _project_fk(),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("probability", sa.Integer(), nullable=False),
        sa.Column("impact", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("stakeholders.id", ondelete="SET NULL")),
        sa.CheckConstraint("probability BETWEEN 1 AND 5", name="probability_range"),
        sa.CheckConstraint("impact BETWEEN 1 AND 5", name="impact_range"),
    )


def _create_finance_and_decisions() -> None:
    op.create_table(
        "budget_lines",
        *_base_columns(),
        _project_fk(),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("planned_cad", sa.Numeric(14, 2), nullable=False),
        sa.Column("actual_cad", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("planned_cad >= 0", name="planned_non_negative"),
    )
    op.create_table(
        "decisions",
        *_base_columns(),
        _project_fk(),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("action_class", sa.String(16), nullable=False),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("proposed_by_agent", sa.String(80), nullable=False),
        sa.Column("decided_by", sa.String(120)),
        sa.Column("decided_at", _TS),
        sa.Column("reason", sa.Text()),
        sa.CheckConstraint(
            "status = 'proposed' OR decided_by IS NOT NULL", name="decided_by_required"
        ),
        sa.CheckConstraint(
            "status NOT IN ('modified', 'rejected') OR reason IS NOT NULL", name="reason_required"
        ),
    )


def _create_audit_and_knowledge() -> None:
    op.create_table(
        "agent_log",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("created_at", _TS, server_default=sa.func.now(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False, index=True),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="RESTRICT"),
            index=True,
        ),
        sa.Column("agent", sa.String(80), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("action_class", sa.String(16), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("prev_hash", sa.String(64)),
        sa.Column("entry_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("signature", sa.String(256)),
    )
    op.execute(_APPEND_ONLY_TRIGGER)
    op.create_table(
        "knowledge_documents",
        *_base_columns(),
        _project_fk(nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("provenance", sa.String(500), nullable=False),
        sa.Column("content_sha256", sa.String(64), nullable=False),
        sa.Column("validated_by", sa.String(120)),
        sa.Column("validated_at", _TS),
        sa.CheckConstraint(
            "(validated_by IS NULL) = (validated_at IS NULL)", name="validation_consistent"
        ),
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _create_projects()
    _create_work_items()
    _create_people_and_risks()
    _create_finance_and_decisions()
    _create_audit_and_knowledge()


def downgrade() -> None:
    op.drop_table("knowledge_documents")
    op.execute("DROP TRIGGER IF EXISTS agent_log_no_truncate ON agent_log")
    op.execute("DROP TRIGGER IF EXISTS agent_log_no_update_delete ON agent_log")
    op.execute("DROP FUNCTION IF EXISTS agent_log_append_only()")
    for table in (
        "agent_log",
        "decisions",
        "budget_lines",
        "risks",
        "stakeholders",
        "tasks",
        "resources",
        "deliverables",
        "projects",
        "portfolios",
    ):
        op.drop_table(table)
