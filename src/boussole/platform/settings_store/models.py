"""Tables de paramétrage : modèle par agent, skills versionnés, coûts LLM."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from boussole.core.models import Base


class AgentSetting(Base):
    """Choix de l'humain; absent = valeur par défaut du catalogue."""

    __tablename__ = "agent_settings"

    agent_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    model: Mapped[str] = mapped_column(String(200))
    updated_by: Mapped[str] = mapped_column(String(120))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SkillVersion(Base):
    """Historique en ajout seul : on ne modifie jamais une version, on en crée une."""

    __tablename__ = "skill_versions"
    __table_args__ = (
        UniqueConstraint("agent_id", "version", name="uq_skill_versions_agent_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[int]
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(16))
    author: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LlmUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    agent: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(200))
    prompt_tokens: Mapped[int]
    completion_tokens: Mapped[int]
    cost_cad: Mapped[Decimal] = mapped_column(Numeric(12, 6))


SETTINGS_TABLES = tuple(
    Base.metadata.tables[name] for name in ("agent_settings", "skill_versions", "llm_usage")
)
