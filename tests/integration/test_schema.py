"""Le schéma migré applique les règles du domaine dans la base elle-même."""

import uuid

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.integration


def _insert_project(engine: Engine) -> uuid.UUID:
    project_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO projects (id, name, approach) VALUES (:id, 'Pilote', 'undecided')"),
            {"id": project_id},
        )
    return project_id


def _insert_log_entry(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO agent_log (correlation_id, agent, action, action_class, payload,"
                " entry_hash) VALUES (:cid, 'test', 'lire', 'read', '{}', :hash)"
            ),
            {"cid": uuid.uuid4(), "hash": uuid.uuid4().hex * 2},
        )


def test_migrations_match_the_model(alembic_config: Config, engine: Engine) -> None:
    command.check(alembic_config)


@pytest.mark.parametrize(
    "statement",
    ["UPDATE agent_log SET agent = 'pirate'", "DELETE FROM agent_log", "TRUNCATE agent_log"],
)
def test_agent_log_is_append_only(engine: Engine, statement: str) -> None:
    _insert_log_entry(engine)
    with pytest.raises(DBAPIError, match="ajout seul"), engine.begin() as conn:
        conn.execute(text(statement))


def test_decided_decision_requires_a_named_human(engine: Engine) -> None:
    project_id = _insert_project(engine)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO decisions (id, project_id, title, rationale, action_class, status,"
                " proposed_by_agent) VALUES (:id, :pid, 'Clore', 'Fin', 'irreversible',"
                " 'approved', 'closing')"
            ),
            {"id": uuid.uuid4(), "pid": project_id},
        )


def test_rejected_decision_requires_a_reason(engine: Engine) -> None:
    project_id = _insert_project(engine)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO decisions (id, project_id, title, rationale, action_class, status,"
                " proposed_by_agent, decided_by) VALUES (:id, :pid, 'Clore', 'Fin',"
                " 'irreversible', 'rejected', 'closing', 'Zakaria')"
            ),
            {"id": uuid.uuid4(), "pid": project_id},
        )


def test_risk_scores_are_bounded(engine: Engine) -> None:
    project_id = _insert_project(engine)
    with pytest.raises(IntegrityError), engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO risks (id, project_id, title, probability, impact, status)"
                " VALUES (:id, :pid, 'Retard', 9, 3, 'identified')"
            ),
            {"id": uuid.uuid4(), "pid": project_id},
        )
