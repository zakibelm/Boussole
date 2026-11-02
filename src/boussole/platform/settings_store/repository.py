"""Lecture et écriture des paramètres d'agents. Le catalogue fournit les défauts."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from boussole.agents.catalog import Catalog
from boussole.agents.pmbok_skills import PmbokSkills
from boussole.core.database import serialize_writes
from boussole.platform.llm_gateway.budget import (
    RESERVATION_TTL,
    Reservation,
    UsageRecord,
    fits,
    refusal,
)
from boussole.platform.settings_store.models import (
    AgentSetting,
    LlmReservation,
    LlmUsage,
    SkillVersion,
)


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

    @property
    def catalog(self) -> Catalog:
        return self._catalog

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

    def adopt_default(self, agent_id: str, author: str) -> list[SkillView]:
        """Verse le skill par défaut du catalogue à l'historique, comme nouvelle version.

        Sans historique, la version précédente du catalogue (si connue) est versée d'abord :
        le retour arrière reste possible depuis Paramètres. Un skill modifié par le PMO est
        remplacé par le défaut, mais reste dans l'historique. Sans effet si la dernière
        version est déjà le défaut. Renvoie les versions créées.
        """
        if not self.default_pending(agent_id):
            return []
        spec = self._catalog.get(agent_id)
        created: list[SkillView] = []
        if spec.previous_skill and not self.skill_history(agent_id):
            created.append(
                self._save_default(agent_id, spec.previous_skill, author, spec.skill_version - 1)
            )
        created.append(self._save_default(agent_id, spec.skill.strip(), author, spec.skill_version))
        return created

    def default_pending(self, agent_id: str) -> bool:
        """Vrai si adopt_default créerait une version : la dernière version diffère du
        défaut, ou aucun historique alors qu'une version précédente est connue."""
        spec = self._catalog.get(agent_id)
        history = self.skill_history(agent_id)
        if history:
            return history[0].text != spec.skill.strip()
        return spec.previous_skill is not None

    def _save_default(self, agent_id: str, text: str, author: str, version: int) -> SkillView:
        reason = f"Défaut du catalogue, version {version}"
        return self.save_skill(agent_id, text, author, SkillSource.DEFAULT, reason)

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
    """Registre des coûts en base. Les réservations y sont partagées par tous les
    processus (workers, commandes), sous le même verrou que le journal d'audit."""

    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def total_spent_cad(self) -> Decimal:
        with self._sessions() as session:
            return _spent(session)

    def record(self, entry: UsageRecord) -> None:
        with self._sessions.begin() as session:
            session.add(_usage(entry))

    def reserve(self, amount: Decimal, cap: Decimal, agent: str, model: str) -> Reservation:
        now = datetime.now(UTC)
        with self._sessions.begin() as session:
            serialize_writes(session)
            session.execute(delete(LlmReservation).where(LlmReservation.expires_at <= now))
            reserved = Decimal(
                str(session.scalar(select(func.coalesce(func.sum(LlmReservation.amount_cad), 0))))
            )
            if not fits(_spent(session), reserved, amount, cap):
                raise refusal(cap, reserved, amount)
            reservation = Reservation(uuid.uuid4().hex, amount)
            session.add(
                LlmReservation(
                    id=reservation.id,
                    created_at=now,
                    expires_at=now + RESERVATION_TTL,
                    agent=agent,
                    model=model,
                    amount_cad=amount,
                )
            )
            return reservation

    def settle(self, reservation: Reservation, entry: UsageRecord | None) -> None:
        with self._sessions.begin() as session:
            serialize_writes(session)
            session.execute(delete(LlmReservation).where(LlmReservation.id == reservation.id))
            if entry is not None:
                session.add(_usage(entry))


def _spent(session: Session) -> Decimal:
    total = session.scalar(select(func.coalesce(func.sum(LlmUsage.cost_cad), 0)))
    return Decimal(str(total))


def _usage(entry: UsageRecord) -> LlmUsage:
    return LlmUsage(
        agent=entry.agent,
        model=entry.model,
        prompt_tokens=entry.usage.prompt_tokens,
        completion_tokens=entry.usage.completion_tokens,
        cost_cad=entry.usage.cost_cad,
    )


def _view(row: SkillVersion) -> SkillView:
    return SkillView(row.agent_id, row.version, row.text, row.source, row.author, row.reason)
