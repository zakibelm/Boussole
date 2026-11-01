"""Créer un projet en une conversation : le sélecteur propose, l'humain décide (ADR 0003).

Recommander l'approche est une écriture réversible de niveau augmentation : le
portail d'action la journalise comme proposition, puis ne l'applique qu'avec la
validation d'un humain nommé dont le rôle est autorisé (config/autonomy.yaml).
"""

import re
import uuid
from collections.abc import Callable

from boussole.agents.answer import Answerer, SourcedAnswer
from boussole.core.enums import Approach, DecisionStatus
from boussole.platform.guardrails.gate import ActionGate
from boussole.platform.guardrails.policy import ActionRequest, Approval, Verdict
from boussole.projects.repository import APPROACH_LABELS, ProjectRepository

SELECTOR = "selector"
RECOMMEND = "recommend_approach"
INTAKE_QUESTION = (
    "Selon les critères du PMBOK (livrables, projet, organisation), quelle approche de "
    "développement convient à ce projet : prédictive, adaptative ou hybride ? Termine par "
    "une ligne « Approche recommandée : prédictive », « Approche recommandée : adaptative » "
    "ou « Approche recommandée : hybride »."
)
_RECOMMENDED = re.compile(
    r"approche\s+recommand[ée]e\s*:?\s*\**\s*(pr[ée]dictive|adaptative|hybride)", re.IGNORECASE
)
_FROM_LABEL = {
    "predictive": Approach.PREDICTIVE,
    "prédictive": Approach.PREDICTIVE,
    "adaptative": Approach.ADAPTIVE,
    "hybride": Approach.HYBRID,
}


class DecisionRefusedError(PermissionError):
    """Le portail d'action a refusé la décision (rôle non autorisé, hors projet…)."""


def parse_approach(text: str) -> Approach | None:
    """Dernière ligne « Approche recommandée : … » de la réponse du sélecteur."""
    found = _RECOMMENDED.findall(text)
    return _FROM_LABEL[found[-1].lower()] if found else None


def rationale(answer: SourcedAnswer) -> str:
    """Réponse, sources et coût : ce que l'humain lit avant de décider."""
    sources = "\n".join(f"[{i}] {c}" for i, c in enumerate(answer.citations, start=1))
    return (
        f"{answer.text}\n\nSources :\n{sources or 'aucune'}\n\n"
        f"Modèle : {answer.model} · coût : {answer.cost_cad} $ CA"
    )


class ProjectAssistant:
    def __init__(
        self,
        projects: ProjectRepository,
        gate: ActionGate,
        answerer: Callable[[], Answerer],
        operator: str,
        role: str,
    ) -> None:
        self.projects = projects
        self._gate = gate
        self._answerer = answerer
        self._operator = operator
        self._role = role

    def propose_approach(self, project_id: uuid.UUID) -> uuid.UUID:
        project = self.projects.get(project_id)
        answer = self._answerer().answer(
            SELECTOR, INTAKE_QUESTION, project_id, context=project.card()
        )
        approach = parse_approach(answer.text)
        request = self._request(project_id, approach)
        result = self._gate.act(request, lambda: None, answer.correlation_id)
        if result.decision.verdict is Verdict.DENY:
            raise DecisionRefusedError(result.decision.reason)
        title = f"Approche {APPROACH_LABELS[approach]}" if approach else "Approche à décider"
        return self.projects.add_decision(project_id, title, rationale(answer), SELECTOR)

    def decide(
        self, project_id: uuid.UUID, decision_id: uuid.UUID, approach: Approach, reason: str
    ) -> None:
        """Approuver la proposition, ou choisir une autre approche en disant pourquoi."""
        if approach is Approach.UNDECIDED:
            raise ValueError("Choisis une approche.")
        proposed = parse_approach(self.projects.decision(project_id, decision_id).rationale)
        status = DecisionStatus.APPROVED if approach is proposed else DecisionStatus.MODIFIED
        if status is DecisionStatus.MODIFIED and not reason.strip():
            raise ValueError("Une approche différente de la proposition demande une raison.")
        result = self._gate.act(
            self._request(project_id, approach),
            lambda: self.projects.settle(
                project_id, decision_id, status, self._operator, reason.strip() or None, approach
            ),
            uuid.uuid4(),
            Approval(self._operator, self._role),
        )
        if not result.executed:
            raise DecisionRefusedError(result.decision.reason)

    def reject(self, project_id: uuid.UUID, decision_id: uuid.UUID, reason: str) -> None:
        if not reason.strip():
            raise ValueError("Un refus demande une raison.")
        if self.projects.decision(project_id, decision_id).status is not DecisionStatus.PROPOSED:
            raise ValueError("Cette décision est déjà prise.")
        self._gate.record(
            self._request(project_id, None),
            uuid.uuid4(),
            {"human": "rejected", "by": self._operator, "role": self._role},
        )
        self.projects.settle(
            project_id, decision_id, DecisionStatus.REJECTED, self._operator, reason.strip()
        )

    def ask(self, project_id: uuid.UUID, agent_id: str, question: str) -> SourcedAnswer:
        """Chat limité au projet courant : la fiche du projet accompagne la question."""
        if not question.strip():
            raise ValueError("Pose une question.")
        project = self.projects.get(project_id)
        return self._answerer().answer(agent_id, question, project_id, context=project.card())

    @staticmethod
    def _request(project_id: uuid.UUID, approach: Approach | None) -> ActionRequest:
        payload: dict[str, object] = {"approach": approach.value if approach else None}
        return ActionRequest(RECOMMEND, SELECTOR, project_id, project_id, payload=payload)
