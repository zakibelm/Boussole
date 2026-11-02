"""Red team du 1er novembre 2026, constat 3 : suppressions dans le journal.

Sans ancre, supprimer la fin du journal ou une entrée de branche morte (laissée par
un embranchement documenté) passait inaperçu. Une ancre signée couvre toutes les
entrées présentes; l'ancre conservée hors du serveur couvre la fin du journal.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from boussole.core.enums import ActionClass
from boussole.core.models import AgentLogEntry
from boussole.platform.audit import log as audit_log
from boussole.platform.audit.log import RESUME_ACTION, AuditEvent, AuditLog
from tests.guardrails_support import audit_sessions, make_audit


def _event(name: str) -> AuditEvent:
    return AuditEvent(uuid.uuid4(), "domain.risk", name, ActionClass.READ, None, {})


def _delete(sessions: sessionmaker[Session], where: str) -> None:
    with sessions.begin() as session:
        session.execute(text("DROP TRIGGER IF EXISTS agent_log_no_delete"))
        session.execute(text(f"DELETE FROM agent_log WHERE {where}"))  # noqa: S608


def _with_documented_fork(sessions: sessionmaker[Session], audit: AuditLog) -> None:
    """e1, e2 sur e1, e3 aussi sur e1 (écriture simultanée), e4 sur e3, puis reprise."""
    key = audit._key()
    first = audit.append(_event("e1"))
    audit.append(_event("e2"))
    with sessions.begin() as session:
        parent = session.scalar(select(AgentLogEntry).where(AgentLogEntry.id == first))
        assert parent is not None
        event, at = _event("e3"), datetime.now(UTC)
        entry_hash = audit_log._hash(parent.entry_hash, at, event)
        session.add(
            AgentLogEntry(
                created_at=at,
                correlation_id=event.correlation_id,
                agent=event.agent,
                action=event.action,
                action_class=event.action_class,
                payload={},
                prev_hash=parent.entry_hash,
                entry_hash=entry_hash,
                signature=audit_log._sign(key, entry_hash),
            )
        )
    audit.append(_event("e4"))
    fork = audit.forks()
    audit.append(
        AuditEvent(uuid.uuid4(), "humain:z", RESUME_ACTION, ActionClass.READ, None, {"forks": fork})
    )
    assert audit.verify().ok


def test_dead_branch_deletion_is_detected_after_an_anchor() -> None:
    sessions = audit_sessions()
    audit = make_audit(sessions)
    _with_documented_fork(sessions, audit)
    audit.anchor("Zakaria")
    _delete(sessions, "action = 'e2'")
    report = audit.verify()
    assert not report.ok and "avant l'ancre" in (report.reason or "")


def test_tail_deletion_is_detected_with_the_external_anchor() -> None:
    sessions = audit_sessions()
    audit = make_audit(sessions)
    for n in range(3):
        audit.append(_event(f"e{n}"))
    anchor = audit.anchor("Zakaria")
    audit.append(_event("après l'ancre"))
    assert audit.verify(anchor).ok
    _delete(sessions, f"id >= {anchor[0]}")  # l'ancre et la suite disparaissent
    assert audit.verify().ok  # limite assumée : sans ancre externe, rien à comparer
    report = audit.verify(anchor)
    assert not report.ok and "ancre externe" in (report.reason or "")


def test_a_different_external_anchor_is_refused() -> None:
    audit = make_audit()
    audit.append(_event("e1"))
    entry, _ = audit.anchor("Zakaria")
    assert not audit.verify((entry, "0" * 64)).ok


def test_anchor_cli_prints_a_line_that_verify_accepts(monkeypatch: object, capsys: object) -> None:
    import pytest

    from boussole.platform.audit import cli

    assert isinstance(monkeypatch, pytest.MonkeyPatch)
    assert isinstance(capsys, pytest.CaptureFixture)
    audit = make_audit()
    audit.append(_event("e1"))
    monkeypatch.setattr(cli, "_audit", lambda: audit)
    assert cli.main(["anchor"]) == 0
    line = capsys.readouterr().out.splitlines()[1]
    assert cli.main(["verify", "--expect", line]) == 0
    assert cli.main(["verify", "--expect", line.split(":")[0] + ":" + "f" * 64]) == 3
