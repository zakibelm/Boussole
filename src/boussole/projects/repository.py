"""Projets : création, décisions et tableau de bord. Les chiffres viennent des données,
jamais d'un modèle (ADR 0003)."""

import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from boussole.core.enums import ActionClass, Approach, DecisionStatus, RiskStatus, WorkStatus
from boussole.core.models import BudgetLine, Decision, Deliverable, Project, Risk, Task

CRITICAL_RISK_SCORE = 15  # probabilité × impact, échelles de 1 à 5
APPROACH_LABELS = {
    Approach.UNDECIDED: "à décider",
    Approach.PREDICTIVE: "prédictive",
    Approach.ADAPTIVE: "adaptative",
    Approach.HYBRID: "hybride",
}


@dataclass(frozen=True)
class ProjectView:
    id: uuid.UUID
    name: str
    description: str
    approach: Approach
    created_at: datetime | None

    @property
    def approach_label(self) -> str:
        return APPROACH_LABELS[self.approach]

    def card(self) -> str:
        """Fiche transmise aux agents, comme donnée."""
        return (
            f"Nom : {self.name}\nApproche actuelle : {self.approach_label}\n"
            f"Description : {self.description or 'aucune'}"
        )


@dataclass(frozen=True)
class DecisionView:
    id: uuid.UUID
    title: str
    rationale: str
    status: DecisionStatus
    proposed_by_agent: str
    decided_by: str | None
    reason: str | None
    created_at: datetime | None


@dataclass(frozen=True)
class RiskLine:
    title: str
    score: int


@dataclass(frozen=True)
class Dashboard:
    deliverables_total: int
    deliverables_done: int
    tasks_by_status: dict[WorkStatus, int]
    tasks_overdue: int
    risks_open: int
    top_risks: tuple[RiskLine, ...]
    budget_planned_cad: Decimal
    budget_actual_cad: Decimal

    @property
    def tasks_total(self) -> int:
        return sum(self.tasks_by_status.values())

    @property
    def budget_consumed_pct(self) -> int | None:
        if not self.budget_planned_cad:
            return None
        return round(self.budget_actual_cad / self.budget_planned_cad * 100)

    def summary(self) -> str:
        """Les chiffres du tableau de bord, en texte, pour les agents."""
        if not (
            self.deliverables_total
            or self.tasks_total
            or self.risks_open
            or self.budget_planned_cad
        ):
            return "Aucune donnée saisie (livrables, tâches, risques, budget)."
        statuses = ", ".join(f"{s.value} {n}" for s, n in sorted(self.tasks_by_status.items()))
        risks = "; ".join(f"{r.title} (score {r.score})" for r in self.top_risks) or "aucun"
        pct = self.budget_consumed_pct
        return (
            f"Livrables terminés : {self.deliverables_done} sur {self.deliverables_total}\n"
            f"Tâches : {self.tasks_total} ({statuses or 'aucune'}), en retard : "
            f"{self.tasks_overdue}\n"
            f"Risques ouverts : {self.risks_open}; critiques : {risks}\n"
            f"Budget : {self.budget_actual_cad} $ CA réels sur {self.budget_planned_cad} $ CA "
            f"prévus ({pct if pct is not None else '—'} %)"
        )


class ProjectRepository:
    def __init__(self, sessions: sessionmaker[Session]) -> None:
        self._sessions = sessions

    def create(self, name: str, description: str) -> uuid.UUID:
        name = name.strip()
        if not name:
            raise ValueError("Le projet doit avoir un nom.")
        with self._sessions.begin() as session:
            project = Project(name=name[:200], description=description.strip() or None)
            session.add(project)
            session.flush()
            return project.id

    def get(self, project_id: uuid.UUID) -> ProjectView:
        with self._sessions() as session:
            project = session.get(Project, project_id)
            if project is None:
                raise KeyError(project_id)
            return _project(project)

    def all(self) -> list[ProjectView]:
        with self._sessions() as session:
            rows = session.scalars(select(Project).order_by(Project.created_at.desc()))
            return [_project(p) for p in rows]

    def decisions(self, project_id: uuid.UUID) -> list[DecisionView]:
        with self._sessions() as session:
            rows = session.scalars(
                select(Decision)
                .where(Decision.project_id == project_id)
                .order_by(Decision.created_at.desc())
            )
            return [_decision(d) for d in rows]

    def pending_decision(self, project_id: uuid.UUID) -> DecisionView | None:
        pending = [d for d in self.decisions(project_id) if d.status is DecisionStatus.PROPOSED]
        return pending[0] if pending else None

    def add_decision(
        self, project_id: uuid.UUID, title: str, rationale: str, agent: str
    ) -> uuid.UUID:
        """Une nouvelle proposition remplace la précédente encore en attente."""
        with self._sessions.begin() as session:
            for old in session.scalars(
                select(Decision).where(
                    Decision.project_id == project_id,
                    Decision.status == DecisionStatus.PROPOSED,
                )
            ):
                _settle(
                    old,
                    DecisionStatus.REJECTED,
                    "Boussole",
                    "Remplacée par une nouvelle proposition",
                )
            decision = Decision(
                project_id=project_id,
                title=title,
                rationale=rationale,
                action_class=ActionClass.REVERSIBLE_WRITE,
                proposed_by_agent=agent,
            )
            session.add(decision)
            session.flush()
            return decision.id

    def decision(self, project_id: uuid.UUID, decision_id: uuid.UUID) -> DecisionView:
        with self._sessions() as session:
            return _decision(_owned(session, project_id, decision_id))

    def settle(
        self,
        project_id: uuid.UUID,
        decision_id: uuid.UUID,
        status: DecisionStatus,
        decided_by: str,
        reason: str | None,
        approach: Approach | None = None,
    ) -> None:
        with self._sessions.begin() as session:
            decision = _owned(session, project_id, decision_id)
            if decision.status is not DecisionStatus.PROPOSED:
                raise ValueError("Cette décision est déjà prise.")
            _settle(decision, status, decided_by, reason)
            if approach is not None:
                session.get_one(Project, project_id).approach = approach

    def dashboard(self, project_id: uuid.UUID, today: date) -> Dashboard:
        with self._sessions() as session:
            deliverables = list(
                session.scalars(select(Deliverable).where(Deliverable.project_id == project_id))
            )
            tasks = list(session.scalars(select(Task).where(Task.project_id == project_id)))
            risks = list(
                session.scalars(
                    select(Risk).where(
                        Risk.project_id == project_id, Risk.status != RiskStatus.CLOSED
                    )
                )
            )
            planned, actual = session.execute(
                select(
                    func.coalesce(func.sum(BudgetLine.planned_cad), 0),
                    func.coalesce(func.sum(BudgetLine.actual_cad), 0),
                ).where(BudgetLine.project_id == project_id)
            ).one()
        ranked = sorted(risks, key=lambda r: r.probability * r.impact, reverse=True)
        return Dashboard(
            deliverables_total=len(deliverables),
            deliverables_done=sum(d.status is WorkStatus.DONE for d in deliverables),
            tasks_by_status=dict(Counter(t.status for t in tasks)),
            tasks_overdue=sum(_overdue(t, today) for t in tasks),
            risks_open=len(risks),
            top_risks=tuple(
                RiskLine(r.title, r.probability * r.impact)
                for r in ranked[:3]
                if r.probability * r.impact >= CRITICAL_RISK_SCORE
            ),
            budget_planned_cad=Decimal(planned),
            budget_actual_cad=Decimal(actual),
        )


def _overdue(task: Task, today: date) -> bool:
    finished = task.status in (WorkStatus.DONE, WorkStatus.CANCELLED)
    return task.due_date is not None and task.due_date < today and not finished


def _owned(session: Session, project_id: uuid.UUID, decision_id: uuid.UUID) -> Decision:
    decision = session.get(Decision, decision_id)
    if decision is None or decision.project_id != project_id:
        raise KeyError(decision_id)
    return decision


def _settle(decision: Decision, status: DecisionStatus, by: str, reason: str | None) -> None:
    decision.status = status
    decision.decided_by = by
    decision.decided_at = datetime.now(UTC)
    decision.reason = reason


def _project(row: Project) -> ProjectView:
    return ProjectView(row.id, row.name, row.description or "", row.approach, row.created_at)


def _decision(row: Decision) -> DecisionView:
    return DecisionView(
        row.id,
        row.title,
        row.rationale,
        row.status,
        row.proposed_by_agent,
        row.decided_by,
        row.reason,
        row.created_at,
    )
