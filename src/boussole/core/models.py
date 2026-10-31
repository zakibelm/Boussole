"""Modèle de données de Boussole. Toute évolution passe par une migration Alembic."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Identity,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from boussole.core.enums import (
    ActionClass,
    Approach,
    DecisionStatus,
    KnowledgeSource,
    ResourceKind,
    RiskStatus,
    WorkStatus,
)

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _enum(enum_cls: type[Any]) -> Enum:
    """Stocke la valeur (et non le nom) de l'énumération."""
    return Enum(enum_cls, values_callable=lambda e: [m.value for m in e], native_enum=False)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class _Entity:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class _ProjectScoped(_Entity):
    """Toute donnée de projet porte son projet : base des droits par projet."""

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )


class Portfolio(_Entity, Base):
    __tablename__ = "portfolios"

    name: Mapped[str] = mapped_column(String(200))


class Project(_Entity, Base):
    __tablename__ = "projects"

    portfolio_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("portfolios.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    approach: Mapped[Approach] = mapped_column(_enum(Approach), default=Approach.UNDECIDED)


class Deliverable(_ProjectScoped, Base):
    __tablename__ = "deliverables"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[WorkStatus] = mapped_column(_enum(WorkStatus), default=WorkStatus.TODO)
    due_date: Mapped[date | None] = mapped_column(Date)


class Resource(_ProjectScoped, Base):
    __tablename__ = "resources"

    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[ResourceKind] = mapped_column(_enum(ResourceKind))
    capacity_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))


class Task(_ProjectScoped, Base):
    __tablename__ = "tasks"

    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deliverables.id", ondelete="SET NULL")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("resources.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300))
    status: Mapped[WorkStatus] = mapped_column(_enum(WorkStatus), default=WorkStatus.TODO)
    due_date: Mapped[date | None] = mapped_column(Date)


class Stakeholder(_ProjectScoped, Base):
    """Minimisation (Loi 25) : ni courriel, ni téléphone, ni texte brut de sentiment."""

    __tablename__ = "stakeholders"
    __table_args__ = (
        CheckConstraint("influence BETWEEN 1 AND 5", name="influence_range"),
        CheckConstraint("interest BETWEEN 1 AND 5", name="interest_range"),
    )

    display_name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(120))
    influence: Mapped[int] = mapped_column(default=3)
    interest: Mapped[int] = mapped_column(default=3)
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Risk(_ProjectScoped, Base):
    __tablename__ = "risks"
    __table_args__ = (
        CheckConstraint("probability BETWEEN 1 AND 5", name="probability_range"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="impact_range"),
    )

    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    probability: Mapped[int]
    impact: Mapped[int]
    status: Mapped[RiskStatus] = mapped_column(_enum(RiskStatus), default=RiskStatus.IDENTIFIED)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("stakeholders.id", ondelete="SET NULL")
    )


class BudgetLine(_ProjectScoped, Base):
    """Montants en dollars canadiens uniquement."""

    __tablename__ = "budget_lines"
    __table_args__ = (CheckConstraint("planned_cad >= 0", name="planned_non_negative"),)

    category: Mapped[str] = mapped_column(String(120))
    planned_cad: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    actual_cad: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"))


class Decision(_ProjectScoped, Base):
    """Une décision irréversible n'est approuvée que par un humain nommé."""

    __tablename__ = "decisions"
    __table_args__ = (
        CheckConstraint(
            "status = 'proposed' OR decided_by IS NOT NULL", name="decided_by_required"
        ),
        CheckConstraint(
            "status NOT IN ('modified', 'rejected') OR reason IS NOT NULL",
            name="reason_required",
        ),
    )

    title: Mapped[str] = mapped_column(String(300))
    rationale: Mapped[str] = mapped_column(Text)
    action_class: Mapped[ActionClass] = mapped_column(_enum(ActionClass))
    status: Mapped[DecisionStatus] = mapped_column(
        _enum(DecisionStatus), default=DecisionStatus.PROPOSED
    )
    proposed_by_agent: Mapped[str] = mapped_column(String(80))
    decided_by: Mapped[str | None] = mapped_column(String(120))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)


class AgentLogEntry(Base):
    """Journal d'agent en ajout seul : un déclencheur refuse UPDATE et DELETE.

    Chaque entrée est chaînée à la précédente par empreinte; la signature est
    posée par le module d'audit (phase 0, tâche 5).
    """

    __tablename__ = "agent_log"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), Identity(always=True), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    correlation_id: Mapped[uuid.UUID] = mapped_column(index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"), index=True
    )
    agent: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(120))
    action_class: Mapped[ActionClass] = mapped_column(_enum(ActionClass))
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB(), "postgresql"), default=dict
    )
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True)
    signature: Mapped[str | None] = mapped_column(String(256))


class KnowledgeDocument(_Entity, Base):
    """Document de connaissance : métadonnées et provenance, jamais le texte du PMBOK."""

    __tablename__ = "knowledge_documents"
    __table_args__ = (
        CheckConstraint(
            "(validated_by IS NULL) = (validated_at IS NULL)",
            name="validation_consistent",
        ),
    )

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[KnowledgeSource] = mapped_column(_enum(KnowledgeSource))
    version: Mapped[int] = mapped_column(default=1)
    provenance: Mapped[str] = mapped_column(String(500))
    content_sha256: Mapped[str] = mapped_column(String(64))
    validated_by: Mapped[str | None] = mapped_column(String(120))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
