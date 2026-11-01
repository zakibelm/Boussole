"""Projet fictif de démonstration : des données pour voir le tableau de bord vivre.

python -m boussole.projects.demo

Aucune donnée réelle : organisation, personnes et montants sont inventés.
"""

import sys
import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session, sessionmaker

from boussole.core.enums import RiskStatus, WorkStatus
from boussole.core.models import BudgetLine, Deliverable, Risk, Task
from boussole.projects.repository import ProjectRepository

NAME = "Démo · Portail client de la Coopérative Horizon (fictif)"
DESCRIPTION = (
    "Projet fictif. La Coopérative Horizon, 40 employés, remplace son portail client vieux de "
    "10 ans. Le lot 1 (hébergement, authentification, migration des 12 000 comptes) suit un "
    "contrat à prix fixe et doit être en service le 1er mars, date de fin du contrat de "
    "l'ancien hébergeur. Le lot 2 (nouvelles fonctions en libre-service) n'est pas encore "
    "défini : la direction veut tester des maquettes avec des membres et décider au fur et à "
    "mesure. Une équipe interne de 4 personnes et un intégrateur externe. Budget : 180 000 $ CA."
)
_DELIVERABLES = [
    ("Hébergement et authentification", WorkStatus.DONE, -20),
    ("Migration des 12 000 comptes", WorkStatus.IN_PROGRESS, 25),
    ("Mise en service du lot 1", WorkStatus.TODO, 120),
    ("Maquettes du libre-service testées avec des membres", WorkStatus.IN_PROGRESS, 40),
]
_TASKS = [
    ("Configurer l'authentification à deux facteurs", WorkStatus.DONE, -25),
    ("Script de migration des comptes", WorkStatus.IN_PROGRESS, -3),
    ("Essai de migration sur 500 comptes", WorkStatus.TODO, -1),
    ("Plan de bascule et de retour arrière", WorkStatus.TODO, 30),
    ("Atelier maquettes avec 8 membres", WorkStatus.DONE, -10),
    ("Synthèse des retours de l'atelier", WorkStatus.IN_PROGRESS, 5),
    ("Formation du service à la clientèle", WorkStatus.TODO, 100),
    ("Ancien moteur de recherche", WorkStatus.CANCELLED, -15),
]
_RISKS = [
    ("Données incomplètes dans l'ancien système retardent la migration", 4, 4),
    ("Fin du contrat de l'ancien hébergeur au 1er mars, sans prolongation", 3, 5),
    ("Membres âgés réticents au libre-service", 3, 3),
    ("Départ du développeur principal de l'intégrateur", 2, 4),
]
_BUDGET = [
    ("Intégrateur externe (prix fixe, lot 1)", "95000", "52000"),
    ("Équipe interne", "60000", "21000"),
    ("Hébergement et licences", "25000", "9500"),
]


def seed_demo(sessions: sessionmaker[Session], today: date) -> uuid.UUID:
    project_id = ProjectRepository(sessions).create(NAME, DESCRIPTION)
    with sessions.begin() as session:
        session.add_all(_rows(project_id, today))
    return project_id


def _rows(project_id: uuid.UUID, today: date) -> list[object]:
    def due(days: int) -> date:
        return today + timedelta(days=days)

    rows: list[object] = [
        Deliverable(project_id=project_id, name=n, status=s, due_date=due(d))
        for n, s, d in _DELIVERABLES
    ]
    rows += [Task(project_id=project_id, title=t, status=s, due_date=due(d)) for t, s, d in _TASKS]
    rows += [
        Risk(project_id=project_id, title=t, probability=p, impact=i, status=RiskStatus.IDENTIFIED)
        for t, p, i in _RISKS
    ]
    rows += [
        BudgetLine(
            project_id=project_id,
            category=c,
            planned_cad=Decimal(p),
            actual_cad=Decimal(a),
        )
        for c, p, a in _BUDGET
    ]
    return rows


def main() -> int:
    from boussole.api.services import open_database
    from boussole.config import load_config

    sessions = open_database(load_config())
    project_id = seed_demo(sessions, date.today())
    print(f"Projet fictif créé : {NAME} ({project_id})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
