"""Lecture et écriture des paramètres d'agents. Le catalogue fournit les défauts."""

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from boussole.agents.catalog import Catalog
from boussole.agents.pmbok_skills import PmbokSkills
from boussole.platform.llm_gateway.budget import UsageRecord
from boussole.platform.settings_store.models import AgentSetting, LlmUsage, SkillVersion


class SkillSource(StrEnum):
    DEFAULT = "default"
    MANUAL = "manual"
    AI_REFINED = "ai_refined"
    REVERT = "revert"


@dataclass(frozen=True)
class SkillView:
    agent_id: str
    version: int
    text: str
    source: str
    author: str
    reason: str | None


class SettingsRepository:
    def __init__(
        self,
        sessions: sessionmaker[Session],
        catalog: Catalog,
        pmbok: PmbokSkills | None = None,
    ) -> None:
        self._sessions = sessions
        self._catalog = catalog
        self._pmbok = pmbok

    def effective_model(self, agent_id: str) -> str:
        with self._sessions() as session:
            setting = session.get(AgentSetting, agent_id)
        return setting.model if setting else self._catalog.get(agent_id).default_model

    def set_model(self, agent_id: str, model: str, author: str) -> None:
        self._catalog.get(agent_id)
        with self._sessions.begin() as session:
            setting = session.get(AgentSetting, agent_id)
            if setting is None:
                session.add(AgentSetting(agent_id=agent_id, model=model, updated_by=author))
            else:
                setting.model, setting.updated_by = model, author

    def current_skill(self, agent_id: str) -> SkillView:
        history = self.skill_history(agent_id)
        if history:
            return history[0]
        default = self._catalog.get(agent_id).skill.strip()
        return SkillView(agent_id, 0, default, SkillSource.DEFAULT, "catalogue", None)

    def skill_history(self, agent_id: str) -> list[SkillView]:
        query = (
            select(SkillVersion)
            .where(SkillVersion.agent_id == agent_id)
            .order_by(SkillVersion.version.desc())
        )
        with self._sessions() as session:
            return [_view(row) for row in session.scalars(query)]

    def save_skill(
        self, agent_id: str, text: str, author: str, source: SkillSource, reason: str | None
    ) -> SkillView:
        self._catalog.get(agent_id)
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("Le skill ne peut pas être vide.")
        with self._sessions.begin() as session:
            last = session.scalar(
                select(func.max(SkillVersion.version)).where(SkillVersion.agent_id == agent_id)
            )
            row = SkillVersion(
                agent_id=agent_id,
                version=(last or 0) + 1,
                text=cleaned,
                source=source,
                author=author,
                reason=reason,
            )
            session.add(row)
            session.flush()
            return _view(row)

    def revert_skill(self, agent_id: str, version: int, author: str) -> SkillView:
        target = next((s for s in self.skill_history(agent_id) if s.version == version), None)
        if target is None:
            raise KeyError(f"{agent_id} v{version}")
        reason = f"Retour à la version {version}"
        return self.save_skill(agent_id, target.text, author, SkillSource.REVERT, reason)

    def system_prompt(self, agent_id: str) -> str:
        """Règles communes + skill courant + parties du PMBOK : ce que reçoit le modèle."""
        parts = [self._catalog.shared_rules.strip(), self.current_skill(agent_id).text]
        if note := self.pmbok_note(agent_id):
            parts.append(note)
        return "\n\n".join(parts)

    def pmbok_note(self, agent_id: str) -> str:
        """Le PMBOK en skill vient de la configuration : un skill édité ne peut pas l'effacer."""
        return self._pmbok.note_for(agent_id) if self._pmbok else ""


class SqlUsageLedger:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def total_spent_cad(self) -> Decimal:
        with self._sessions() as session:
            total = session.scalar(select(func.coalesce(func.sum(LlmUsage.cost_cad), 0)))
        return Decimal(str(total))

    def record(self, entry: UsageRecord) -> None:
        with self._sessions.begin() as session:
            session.add(
                LlmUsage(
                    agent=entry.agent,
                    model=entry.model,
                    prompt_tokens=entry.usage.prompt_tokens,
                    completion_tokens=entry.usage.completion_tokens,
                    cost_cad=entry.usage.cost_cad,
                )
            )


def _view(row: SkillVersion) -> SkillView:
    return SkillView(row.agent_id, row.version, row.text, row.source, row.author, row.reason)
