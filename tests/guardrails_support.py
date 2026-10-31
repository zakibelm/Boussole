"""Outils communs aux tests des garde-fous et red team."""

import secrets
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from boussole.agents.catalog import Catalog, load_catalog
from boussole.platform.audit.log import AUDIT_KEY, AuditLog, create_audit_table
from boussole.platform.guardrails.gate import ActionGate
from boussole.platform.guardrails.policy import AutonomyConfig, load_policy
from boussole.platform.secrets import InMemorySecretStore

ROOT = Path(__file__).resolve().parents[1]
CATALOG: Catalog = load_catalog(ROOT / "config" / "agents.yaml")
POLICY: AutonomyConfig = load_policy(ROOT / "config" / "autonomy.yaml")


def audit_sessions() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    create_audit_table(engine)
    return sessionmaker(engine, expire_on_commit=False)


def make_audit(sessions: sessionmaker[Session] | None = None) -> AuditLog:
    store = InMemorySecretStore()
    store.set(AUDIT_KEY, secrets.token_hex(32))
    return AuditLog(sessions or audit_sessions(), store)


def make_gate(audit: AuditLog | None = None) -> ActionGate:
    return ActionGate(POLICY, CATALOG, audit or make_audit())
