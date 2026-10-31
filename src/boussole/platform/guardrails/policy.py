"""Politique d'autonomie : décide, avant toute action, si elle peut avoir effet."""

import re
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, model_validator

from boussole.core.enums import ActionClass, Autonomy

_HOSTNAME = re.compile(r"[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*\.?")
_RESTRICTIVENESS = {Autonomy.AUTOMATION: 0, Autonomy.ASSISTANCE: 1, Autonomy.AUGMENTATION: 2}


class ActionPolicy(BaseModel):
    class_: ActionClass
    level: Autonomy
    approvers: list[str] = []
    description: str = ""

    model_config = {"populate_by_name": True}

    @model_validator(mode="before")
    @classmethod
    def _rename_class(cls, data: dict[str, object]) -> dict[str, object]:
        if "class" in data:
            data = {**data, "class_": data["class"]}
            data.pop("class")
        return data

    @model_validator(mode="after")
    def _irreversible_needs_humans(self) -> "ActionPolicy":
        irreversible = self.class_ is ActionClass.IRREVERSIBLE
        if irreversible and (self.level is not Autonomy.AUGMENTATION or not self.approvers):
            raise ValueError("Une action irréversible exige augmentation et des approbateurs.")
        if self.level is not Autonomy.AUTOMATION and not self.approvers:
            raise ValueError("Une action révisée par un humain exige des approbateurs.")
        return self


class AutonomyConfig(BaseModel):
    actions: dict[str, ActionPolicy]
    network_allowlist: list[str] = []


def load_policy(path: Path) -> AutonomyConfig:
    return AutonomyConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


class Verdict(StrEnum):
    ALLOW = "allow"  # effet immédiat, journalisé
    NEEDS_HUMAN = "needs_human"  # brouillon ou décision : rien sans validation
    DENY = "deny"


@dataclass(frozen=True)
class Approval:
    approver: str  # humain nommé
    role: str


@dataclass(frozen=True)
class ActionRequest:
    action: str
    agent_id: str
    project_id: uuid.UUID | None
    target_project_id: uuid.UUID | None
    destination: str | None = None
    external_sources: tuple[str, ...] = ()  # contenu externe ayant inspiré l'action
    payload: dict[str, object] = field(default_factory=dict)

    @property
    def tainted(self) -> bool:
        return bool(self.external_sources)


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str
    action_class: ActionClass | None = None
    level: Autonomy | None = None
    approvers: tuple[str, ...] = ()


def decide(
    config: AutonomyConfig,
    request: ActionRequest,
    agent_ceiling: Autonomy,
    approval: Approval | None,
) -> Decision:
    """`agent_ceiling` vient du catalogue, jamais de la requête de l'agent."""
    policy = config.actions.get(request.action)
    if policy is None:
        return Decision(Verdict.DENY, f"Action inconnue : {request.action}")
    denial = _scope_denial(config, request)
    if denial:
        return Decision(Verdict.DENY, denial, policy.class_)
    level = policy.level
    if policy.class_ is not ActionClass.READ:
        # Le plafond de l'agent borne les effets, pas la lecture dans son projet.
        level = _most_restrictive(level, agent_ceiling)
        if request.tainted:
            level = _most_restrictive(level, Autonomy.ASSISTANCE)
    approvers = tuple(policy.approvers)
    if level is Autonomy.AUTOMATION:
        return Decision(Verdict.ALLOW, "Automatisation autorisée", policy.class_, level, approvers)
    return _with_human(policy, level, approvers, approval)


def _with_human(
    policy: ActionPolicy, level: Autonomy, approvers: tuple[str, ...], approval: Approval | None
) -> Decision:
    if approval is None:
        return Decision(
            Verdict.NEEDS_HUMAN, "Validation humaine requise", policy.class_, level, approvers
        )
    if not approval.approver.strip():
        return Decision(
            Verdict.DENY, "Validation sans humain nommé", policy.class_, level, approvers
        )
    if approval.role not in approvers:
        reason = f"Le rôle « {approval.role} » ne peut pas valider cette action"
        return Decision(Verdict.DENY, reason, policy.class_, level, approvers)
    reason = f"Validé par {approval.approver} ({approval.role})"
    return Decision(Verdict.ALLOW, reason, policy.class_, level, approvers)


def _scope_denial(config: AutonomyConfig, request: ActionRequest) -> str | None:
    if request.target_project_id is not None and request.target_project_id != request.project_id:
        return "Hors du projet de l'agent"
    if request.destination is not None and not _allowed(
        request.destination, config.network_allowlist
    ):
        return f"Destination hors liste blanche : {request.destination}"
    return None


def _allowed(destination: str, allowlist: list[str]) -> bool:
    host = _host(destination)
    if host is None:
        return False
    domains = (d.lower().rstrip(".") for d in allowlist)
    return any(host == d or host.endswith(f".{d}") for d in domains)


def _host(destination: str) -> str | None:
    """Hôte réel selon RFC 3986; None si l'adresse est ambiguë (échec fermé).

    Un découpage naïf accepterait « https://pirate.com#.openrouter.ai » : l'hôte
    réel est pirate.com, mais la chaîne se termine par le domaine autorisé.
    """
    url = destination if "://" in destination else f"//{destination}"
    try:
        host = urlsplit(url).hostname
    except ValueError:
        return None
    if not host or not _HOSTNAME.fullmatch(host):
        return None
    return host.rstrip(".")


def _most_restrictive(a: Autonomy, b: Autonomy) -> Autonomy:
    return a if _RESTRICTIVENESS[a] >= _RESTRICTIVENESS[b] else b
