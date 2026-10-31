"""Journal d'audit en ajout seul, chaîné par empreinte et signé (HMAC-SHA256).

Seul le portail d'action écrit ici; les agents n'y ont pas accès. La base
refuse UPDATE, DELETE et TRUNCATE (déclencheurs), et `verify` détecte toute
altération de contenu, de chaînage ou de signature.
"""

import hashlib
import hmac
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from boussole.core.enums import ActionClass
from boussole.core.models import AgentLogEntry, Base
from boussole.platform.secrets import SecretStore

AUDIT_KEY = "audit_signing_key"

_SQLITE_APPEND_ONLY = (
    """CREATE TRIGGER IF NOT EXISTS agent_log_no_update BEFORE UPDATE ON agent_log
    BEGIN SELECT RAISE(ABORT, 'agent_log est en ajout seul : UPDATE refusé'); END""",
    """CREATE TRIGGER IF NOT EXISTS agent_log_no_delete BEFORE DELETE ON agent_log
    BEGIN SELECT RAISE(ABORT, 'agent_log est en ajout seul : DELETE refusé'); END""",
)


class MissingSigningKeyError(RuntimeError):
    """Aucune clé de signature : un humain la crée avec `audit.cli init-key`."""


@dataclass(frozen=True)
class AuditEvent:
    correlation_id: uuid.UUID
    agent: str
    action: str
    action_class: ActionClass
    project_id: uuid.UUID | None
    payload: dict[str, Any]


@dataclass(frozen=True)
class VerifyReport:
    entries: int
    first_broken_id: int | None
    reason: str | None

    @property
    def ok(self) -> bool:
        return self.first_broken_id is None


class AuditLog:
    def __init__(self, sessions: sessionmaker[Session], secrets: SecretStore) -> None:
        self._sessions = sessions
        self._secrets = secrets

    def append(self, event: AuditEvent) -> int:
        key = self._key()
        with self._sessions.begin() as session:
            _lock(session)
            prev = session.scalar(
                select(AgentLogEntry.entry_hash).order_by(AgentLogEntry.id.desc()).limit(1)
            )
            created_at = datetime.now(UTC)
            entry_hash = _hash(prev, created_at, event)
            row = AgentLogEntry(
                created_at=created_at,
                correlation_id=event.correlation_id,
                project_id=event.project_id,
                agent=event.agent,
                action=event.action,
                action_class=event.action_class,
                payload=event.payload,
                prev_hash=prev,
                entry_hash=entry_hash,
                signature=_sign(key, entry_hash),
            )
            session.add(row)
            session.flush()
            return row.id

    def verify(self) -> VerifyReport:
        key = self._key()
        prev: str | None = None
        count = 0
        with self._sessions() as session:
            for row in session.scalars(select(AgentLogEntry).order_by(AgentLogEntry.id)):
                count += 1
                problem = _check(row, prev, key)
                if problem:
                    return VerifyReport(count, row.id, problem)
                prev = row.entry_hash
        return VerifyReport(count, None, None)

    def _key(self) -> bytes:
        value = self._secrets.get(AUDIT_KEY)
        if not value:
            raise MissingSigningKeyError("Clé de signature du journal absente.")
        return bytes.fromhex(value)


def create_audit_table(engine: Engine) -> None:
    """Mode local léger (SQLite) : table et déclencheurs d'ajout seul."""
    Base.metadata.create_all(engine, tables=[Base.metadata.tables["agent_log"]])
    with engine.begin() as conn:
        for statement in _SQLITE_APPEND_ONLY:
            conn.execute(text(statement))


def _check(row: AgentLogEntry, prev: str | None, key: bytes) -> str | None:
    if row.prev_hash != prev:
        return "chaînage rompu (entrée supprimée ou insérée)"
    event = AuditEvent(
        row.correlation_id, row.agent, row.action, row.action_class, row.project_id, row.payload
    )
    if _hash(prev, row.created_at, event) != row.entry_hash:
        return "contenu modifié"
    if not hmac.compare_digest(_sign(key, row.entry_hash), row.signature or ""):
        return "signature invalide"
    return None


def _hash(prev: str | None, created_at: datetime, event: AuditEvent) -> str:
    canonical = json.dumps(
        {
            "prev": prev,
            "at": _utc(created_at).isoformat(),
            "correlation_id": str(event.correlation_id),
            "agent": event.agent,
            "action": event.action,
            "class": str(event.action_class),
            "project_id": str(event.project_id) if event.project_id else None,
            "payload": event.payload,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _sign(key: bytes, entry_hash: str) -> str:
    return hmac.new(key, entry_hash.encode(), hashlib.sha256).hexdigest()


def _utc(moment: datetime) -> datetime:
    """SQLite rend des dates naïves : elles ont été écrites en UTC."""
    return moment if moment.tzinfo else moment.replace(tzinfo=UTC)


def _lock(session: Session) -> None:
    """Sérialise les écritures pour que le chaînage reste linéaire."""
    if session.get_bind().dialect.name == "postgresql":
        session.execute(text("SELECT pg_advisory_xact_lock(hashtext('agent_log'))"))
