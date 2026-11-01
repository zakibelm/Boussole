"""Portail d'action : le seul chemin par lequel une action d'agent a un effet.

Séparation lecture et action : `read` n'exécute que des actions de classe
lecture; toute écriture passe par `act`, qui applique la politique d'autonomie.
Chaque décision est journalisée AVANT l'effet; si le journal échoue, rien
n'est exécuté (échec fermé).
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass

from boussole.agents.catalog import Catalog
from boussole.core.enums import ActionClass, Autonomy
from boussole.platform.audit.log import AuditEvent, AuditLog
from boussole.platform.guardrails.policy import (
    ActionRequest,
    Approval,
    AutonomyConfig,
    Decision,
    Verdict,
    decide,
)


class NotAReadError(PermissionError):
    """Une écriture a été demandée par le canal de lecture."""


@dataclass(frozen=True)
class GateResult[T]:
    decision: Decision
    audit_id: int
    value: T | None = None

    @property
    def executed(self) -> bool:
        return self.decision.verdict is Verdict.ALLOW


class ActionGate:
    def __init__(self, policy: AutonomyConfig, catalog: Catalog, audit: AuditLog) -> None:
        self._policy = policy
        self._catalog = catalog
        self._audit = audit

    def read[T](
        self, request: ActionRequest, handler: Callable[[], T], correlation_id: uuid.UUID
    ) -> GateResult[T]:
        policy = self._policy.actions.get(request.action)
        if policy is None or policy.class_ is not ActionClass.READ:
            raise NotAReadError(f"« {request.action} » n'est pas une lecture.")
        return self.act(request, handler, correlation_id)

    def act[T](
        self,
        request: ActionRequest,
        handler: Callable[[], T],
        correlation_id: uuid.UUID,
        approval: Approval | None = None,
    ) -> GateResult[T]:
        decision = self._decide(request, approval)
        audit_id = self._log(request, decision, approval, correlation_id)
        if decision.verdict is not Verdict.ALLOW:
            return GateResult(decision, audit_id)
        try:
            value = handler()
        except Exception as exc:
            self._log_failure(request, decision, correlation_id, exc)
            raise
        return GateResult(decision, audit_id, value)

    def record(
        self, request: ActionRequest, correlation_id: uuid.UUID, outcome: dict[str, object]
    ) -> int:
        """Journalise le résultat d'une action exécutée : repères et compteurs, jamais de texte
        protégé (citations, modèle, coût, empreinte de la réponse)."""
        policy = self._policy.actions.get(request.action)
        action_class = policy.class_ if policy else ActionClass.READ
        payload: dict[str, object] = {"verdict": "done", **outcome}
        return self._audit.append(
            AuditEvent(
                correlation_id,
                request.agent_id,
                request.action,
                action_class,
                request.project_id,
                payload,
            )
        )

    def _decide(self, request: ActionRequest, approval: Approval | None) -> Decision:
        try:
            ceiling = self._catalog.get(request.agent_id).autonomy
        except KeyError:
            return Decision(Verdict.DENY, f"Agent inconnu : {request.agent_id}")
        return decide(self._policy, request, ceiling, approval)

    def _log(
        self,
        request: ActionRequest,
        decision: Decision,
        approval: Approval | None,
        correlation_id: uuid.UUID,
    ) -> int:
        payload: dict[str, object] = {
            "verdict": str(decision.verdict),
            "reason": decision.reason,
            "level": str(decision.level) if decision.level else None,
            "approver": approval.approver if approval else None,
            "approver_role": approval.role if approval else None,
            "external_sources": list(request.external_sources),
            "target_project_id": str(request.target_project_id)
            if request.target_project_id
            else None,
            "destination": request.destination,
        }
        return self._audit.append(
            AuditEvent(
                correlation_id,
                request.agent_id,
                request.action,
                decision.action_class or ActionClass.READ,
                request.project_id,
                payload,
            )
        )

    def _log_failure(
        self, request: ActionRequest, decision: Decision, correlation_id: uuid.UUID, exc: Exception
    ) -> None:
        payload: dict[str, object] = {"verdict": "failed", "error": type(exc).__name__}
        self._audit.append(
            AuditEvent(
                correlation_id,
                request.agent_id,
                request.action,
                decision.action_class or ActionClass.READ,
                request.project_id,
                payload,
            )
        )


__all__ = ["ActionGate", "Autonomy", "GateResult", "NotAReadError"]
