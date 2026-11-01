"""Créer un projet en une conversation : le sélecteur propose, l'humain décide (ADR 0003).

Recommander l'approche est une écriture réversible de niveau augmentation : le
portail d'action la journalise comme proposition, puis ne l'applique qu'avec la
validation d'un humain nommé dont le rôle est autorisé (config/autonomy.yaml).
"""

import re
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from boussole.agents.answer import Answerer, SourcedAnswer
from boussole.core.enums import Approach, DecisionStatus
from boussole.platform.guardrails.gate import ActionGate
from boussole.platform.guardrails.policy import ActionRequest, Approval, Verdict
from boussole.platform.memory_rag.port import PageRange
from boussole.projects.repository import APPROACH_LABELS, ProjectRepository

SELECTOR = "selector"
RECOMMEND = "recommend_approach"
INTAKE_QUESTION = (
    "Selon les critères du PMBOK (livrables, projet, organisation), quelle approche de "
    "développement convient à ce projet : prédictive, adaptative ou hybride ? Réponds en "
    "250 mots au plus : un tableau Critère | Constat | Approche pour les trois critères, puis "
    "« Questions avant de décider » si des informations manquent (équipe, budget, échéance, "
    "contraintes de l'organisation), puis une dernière ligne « Approche recommandée : "
    "prédictive », « Approche recommandée : adaptative » ou « Approche recommandée : hybride »."
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


@dataclass(frozen=True)
class Signer:
    """Humain nommé qui décide, avec son rôle (config/autonomy.yaml, approvers)."""

    name: str
    role: str


class ProjectAssistant:
    def __init__(
        self,
        projects: ProjectRepository,
        gate: ActionGate,
        answerer: Callable[[], Answerer],
        intake_pages: tuple[PageRange, ...] | None = None,
    ) -> None:
        """`intake_pages` : parties du livre sur le choix de l'approche, pour que la
        proposition cite le bon chapitre plutôt que tout le livre."""
        self.projects = projects
        self._gate = gate
        self._answerer = answerer
        self._intake_pages = intake_pages

    def propose_approach(self, project_id: uuid.UUID) -> uuid.UUID:
        answer = self._answerer().answer(
            SELECTOR,
            INTAKE_QUESTION,
            project_id,
            k=8,
            context=self.context(project_id),
            pages=self._intake_pages,
        )
        approach = parse_approach(answer.text)
        request = self._request(project_id, approach)
        result = self._gate.act(request, lambda: None, answer.correlation_id)
        if result.decision.verdict is Verdict.DENY:
            raise DecisionRefusedError(result.decision.reason)
        title = f"Approche {APPROACH_LABELS[approach]}" if approach else "Approche à décider"
        return self.projects.add_decision(project_id, title, rationale(answer), SELECTOR)

    def decide(
        self,
        project_id: uuid.UUID,
        decision_id: uuid.UUID,
        approach: Approach,
        reason: str,
        signer: Signer,
    ) -> None:
        """Approuver la proposition, ou choisir une autre approche en disant pourquoi."""
        if approach is Approach.UNDECIDED:
            raise ValueError("Choisis une approche.")
        proposed = parse_approach(self.projects.decision(project_id, decision_id).rationale)
        status = DecisionStatus.APPROVED if approach is proposed else DecisionStatus.MODIFIED
        if status is DecisionStatus.MODIFIED and not reason.strip():
            raise ValueError("Une approche différente de la proposition demande une raison.")
        self._signed(
            project_id,
            approach,
            signer,
            lambda: self.projects.settle(
                project_id, decision_id, status, signer.name, reason.strip() or None, approach
            ),
        )

    def reject(
        self, project_id: uuid.UUID, decision_id: uuid.UUID, reason: str, signer: Signer
    ) -> None:
        """Un refus est aussi une décision : même rôle exigé, même signature."""
        if not reason.strip():
            raise ValueError("Un refus demande une raison.")
        if self.projects.decision(project_id, decision_id).status is not DecisionStatus.PROPOSED:
            raise ValueError("Cette décision est déjà prise.")
        cid = self._signed(
            project_id,
            None,
            signer,
            lambda: self.projects.settle(
                project_id, decision_id, DecisionStatus.REJECTED, signer.name, reason.strip()
            ),
        )
        outcome: dict[str, object] = {"human": "rejected", "by": signer.name, "role": signer.role}
        self._gate.record(self._request(project_id, None), cid, outcome)

    def ask(self, project_id: uuid.UUID, agent_id: str, question: str) -> SourcedAnswer:
        """Chat limité au projet courant : fiche et chiffres du projet accompagnent la question."""
        if not question.strip():
            raise ValueError("Pose une question.")
        return self._answerer().answer(
            agent_id, question, project_id, context=self.context(project_id)
        )

    def context(self, project_id: uuid.UUID) -> str:
        """Fiche et chiffres du tableau de bord : des données, calculées par Boussole."""
        card = self.projects.get(project_id).card()
        facts = self.projects.dashboard(project_id, date.today()).summary()
        return f"{card}\n\nDonnées du projet (calculées par Boussole) :\n{facts}"

    def _signed(
        self,
        project_id: uuid.UUID,
        approach: Approach | None,
        signer: Signer,
        effect: Callable[[], None],
    ) -> uuid.UUID:
        cid = uuid.uuid4()
        result = self._gate.act(
            self._request(project_id, approach), effect, cid, Approval(signer.name, signer.role)
        )
        if not result.executed:
            raise DecisionRefusedError(result.decision.reason)
        return cid

    @staticmethod
    def _request(project_id: uuid.UUID, approach: Approach | None) -> ActionRequest:
        payload: dict[str, object] = {"approach": approach.value if approach else None}
        return ActionRequest(RECOMMEND, SELECTOR, project_id, project_id, payload=payload)
