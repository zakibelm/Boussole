"""Journal d'audit en ajout seul, chaîné par empreinte et signé (HMAC-SHA256).

Seul le portail d'action écrit ici; les agents n'y ont pas accès. La base
refuse UPDATE, DELETE et TRUNCATE (déclencheurs), et `verify` détecte toute
altération de contenu, de chaînage ou de signature.
"""

import hashlib
import hmac
import json
import threading
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
RESUME_ACTION = "audit_resume"
ANCHOR_ACTION = "audit_anchor"
# Une seule écriture à la fois dans ce processus : sans cela, deux requêtes
# simultanées lisent la même entrée précédente et le chaînage se ramifie.
_WRITE_LOCK = threading.Lock()

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
    documented_forks: tuple[int, ...] = ()

    @property
    def ok(self) -> bool:
        return self.first_broken_id is None


class AuditLog:
    def __init__(self, sessions: sessionmaker[Session], secrets: SecretStore) -> None:
        self._sessions = sessions
        self._secrets = secrets

    def append(self, event: AuditEvent) -> int:
        key = self._key()
        with _WRITE_LOCK, self._sessions.begin() as session:
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

    def verify(self, expected: tuple[int, str] | None = None) -> VerifyReport:
        """Chaînage, contenu et signature. Un embranchement n'est accepté que s'il est
        documenté par une entrée de reprise signée et pointe vers une entrée existante
        (rien n'a été supprimé). Chaque ancre doit correspondre aux entrées qu'elle couvre;
        `expected` (ancre conservée hors du serveur) doit être présente et identique."""
        key = self._key()
        with self._sessions() as session:
            rows = list(session.scalars(select(AgentLogEntry).order_by(AgentLogEntry.id)))
        documented = _documented_forks(rows, key)
        seen: set[str] = set()
        prev: str | None = None
        accepted: list[int] = []
        for row in rows:
            fork = row.prev_hash != prev and row.id in documented and row.prev_hash in seen
            problem = _check(row, row.prev_hash if fork else prev, key)
            if problem:
                return VerifyReport(len(rows), row.id, problem, tuple(accepted))
            if fork:
                accepted.append(row.id)
            seen.add(row.entry_hash)
            prev = row.entry_hash
        broken = _broken_anchor(rows, expected)
        if broken:
            return VerifyReport(len(rows), broken[0], broken[1], tuple(accepted))
        return VerifyReport(len(rows), None, None, tuple(accepted))

    def anchor(self, by: str) -> tuple[int, str]:
        """Ancre signée : empreinte de toutes les entrées présentes, branches mortes
        comprises. Toute suppression antérieure devient détectable; l'ancre affichée,
        conservée hors du serveur, rend aussi détectable la suppression de la fin."""
        with _WRITE_LOCK:
            with self._sessions() as session:
                rows = list(session.scalars(select(AgentLogEntry).order_by(AgentLogEntry.id)))
            through = rows[-1].id if rows else 0
            payload = {"through_id": through, "count": len(rows), "digest": _digest(rows), "by": by}
        entry = self.append(
            AuditEvent(uuid.uuid4(), f"humain:{by}", ANCHOR_ACTION, ActionClass.READ, None, payload)
        )
        return entry, str(payload["digest"])

    def forks(self) -> list[int]:
        """Entrées dont le précédent n'est pas l'entrée juste avant, mais une entrée qui
        existe encore : écritures simultanées, pas suppression."""
        with self._sessions() as session:
            rows = list(session.scalars(select(AgentLogEntry).order_by(AgentLogEntry.id)))
        found, seen, prev = [], set(), None
        for row in rows:
            if row.prev_hash != prev and row.prev_hash in seen:
                found.append(row.id)
            seen.add(row.entry_hash)
            prev = row.entry_hash
        return found

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


def _documented_forks(rows: list[AgentLogEntry], key: bytes) -> set[int]:
    """Identifiants listés par des entrées de reprise intègres et signées."""
    documented: set[int] = set()
    for row in rows:
        if row.action == RESUME_ACTION and _check(row, row.prev_hash, key) is None:
            documented.update(int(i) for i in row.payload.get("forks", []))
    return documented


def _digest(rows: list[AgentLogEntry]) -> str:
    joined = "\n".join(f"{row.id}:{row.entry_hash}" for row in rows)
    return hashlib.sha256(joined.encode()).hexdigest()


def _broken_anchor(
    rows: list[AgentLogEntry], expected: tuple[int, str] | None
) -> tuple[int, str] | None:
    """(identifiant, raison) de la première ancre contredite par les entrées présentes."""
    anchors = {row.id: row for row in rows if row.action == ANCHOR_ACTION}
    for anchor_id, anchor in anchors.items():
        through = int(anchor.payload["through_id"])
        covered = [row for row in rows if row.id <= through]
        if len(covered) != anchor.payload["count"] or _digest(covered) != anchor.payload["digest"]:
            return anchor_id, f"entrée supprimée avant l'ancre {anchor_id}"
    if expected is not None:
        anchor_id, digest = expected
        found = anchors.get(anchor_id)
        if found is None or found.payload["digest"] != digest:
            last = rows[-1].id if rows else 0
            return (
                last,
                f"ancre externe {anchor_id} absente ou différente : fin du journal supprimée",
            )
    return None


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
