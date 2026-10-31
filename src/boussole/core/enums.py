"""Vocabulaire du domaine partagé par les agents, les garde-fous et la base."""

from enum import StrEnum


class Approach(StrEnum):
    UNDECIDED = "undecided"
    PREDICTIVE = "predictive"
    ADAPTIVE = "adaptive"
    HYBRID = "hybrid"


class ActionClass(StrEnum):
    """Classe d'une action, au cœur de la politique d'autonomie (principe 4)."""

    READ = "read"
    REVERSIBLE_WRITE = "reversible_write"
    IRREVERSIBLE = "irreversible"


class WorkStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class RiskStatus(StrEnum):
    IDENTIFIED = "identified"
    MITIGATING = "mitigating"
    CLOSED = "closed"


class DecisionStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"


class ResourceKind(StrEnum):
    HUMAN = "human"
    EQUIPMENT = "equipment"
    MATERIAL = "material"


class KnowledgeSource(StrEnum):
    PMBOK = "pmbok"
    LESSON_LEARNED = "lesson_learned"
    PROJECT_DOCUMENT = "project_document"
