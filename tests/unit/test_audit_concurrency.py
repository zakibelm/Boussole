"""Journal sous écritures simultanées, et reprise documentée d'un embranchement.

Incident du 1er novembre 2026 : trois questions envoyées en même temps ont lu la
même entrée précédente; le chaînage s'est ramifié (entrées 32 et 35).
"""

import secrets
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from boussole.core.database import make_engine
from boussole.core.enums import ActionClass
from boussole.core.models import AgentLogEntry
from boussole.platform.audit.log import (
    AUDIT_KEY,
    RESUME_ACTION,
    AuditEvent,
    AuditLog,
    _hash,
    _sign,
    create_audit_table,
)
from boussole.platform.secrets import InMemorySecretStore

KEY = secrets.token_hex(32)


def _audit(path: Path) -> tuple[AuditLog, sessionmaker[Session]]:
    engine = make_engine(f"sqlite:///{path}")
    create_audit_table(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    store = InMemorySecretStore()
    store.set(AUDIT_KEY, KEY)
    return AuditLog(sessions, store), sessions


def _event(action: str = "search_memory", payload: dict[str, object] | None = None) -> AuditEvent:
    return AuditEvent(uuid.uuid4(), "selector", action, ActionClass.READ, None, payload or {})


def _forge_sibling(sessions: sessionmaker[Session], parent_id: int) -> int:
    """Reproduit l'incident : une entrée signée qui pointe vers un précédent déjà pris."""
    with sessions.begin() as session:
        parent = session.get_one(AgentLogEntry, parent_id)
        event, at = _event(), datetime.now(UTC)
        entry_hash = _hash(parent.entry_hash, at, event)
        row = AgentLogEntry(
            created_at=at,
            correlation_id=event.correlation_id,
            project_id=None,
            agent=event.agent,
            action=event.action,
            action_class=event.action_class,
            payload=event.payload,
            prev_hash=parent.entry_hash,
            entry_hash=entry_hash,
            signature=_sign(bytes.fromhex(KEY), entry_hash),
        )
        session.add(row)
        session.flush()
        return row.id


def test_simultaneous_writes_keep_a_single_chain(tmp_path: Path) -> None:
    audit, _ = _audit(tmp_path / "journal.db")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda _: audit.append(_event()), range(40)))
    report = audit.verify()
    assert report.ok and report.entries == 40 and not report.documented_forks


def test_a_fork_breaks_the_chain_until_a_signed_resume_documents_it(tmp_path: Path) -> None:
    audit, sessions = _audit(tmp_path / "journal.db")
    first = audit.append(_event())
    audit.append(_event())
    fork = _forge_sibling(sessions, first)
    assert audit.verify().first_broken_id == fork
    assert audit.forks() == [fork]
    audit.append(_event(RESUME_ACTION, {"forks": [fork], "reason": "écritures simultanées"}))
    report = audit.verify()
    assert report.ok and report.documented_forks == (fork,)


def test_a_resume_cannot_excuse_a_deletion(tmp_path: Path) -> None:
    audit, sessions = _audit(tmp_path / "journal.db")
    for _ in range(3):
        audit.append(_event())
    with sessions.begin() as session:
        session.execute(text("DROP TRIGGER agent_log_no_delete"))
        session.execute(text("DELETE FROM agent_log WHERE id = 2"))
    audit.append(_event(RESUME_ACTION, {"forks": [3], "reason": "tentative"}))
    assert audit.verify().first_broken_id == 3


def test_a_resume_signed_with_another_key_is_ignored(tmp_path: Path) -> None:
    audit, sessions = _audit(tmp_path / "journal.db")
    first = audit.append(_event())
    audit.append(_event())
    fork = _forge_sibling(sessions, first)
    forger = InMemorySecretStore()
    forger.set(AUDIT_KEY, secrets.token_hex(32))
    AuditLog(sessions, forger).append(_event(RESUME_ACTION, {"forks": [fork]}))
    assert audit.verify().first_broken_id == fork
