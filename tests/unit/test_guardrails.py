"""Politique d'autonomie, portail d'action et journal d'audit."""

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from boussole.core.enums import ActionClass, Autonomy
from boussole.platform.audit.log import AuditEvent, AuditLog, MissingSigningKeyError
from boussole.platform.guardrails.gate import NotAReadError
from boussole.platform.guardrails.policy import (
    ActionPolicy,
    ActionRequest,
    Approval,
    Verdict,
    decide,
)
from boussole.platform.secrets import InMemorySecretStore
from tests.guardrails_support import CATALOG, POLICY, audit_sessions, make_audit, make_gate

PROJECT = uuid.uuid4()
CID = uuid.uuid4()


def _request(action: str, agent: str = "domain.risk", **extra: object) -> ActionRequest:
    return ActionRequest(action, agent, PROJECT, PROJECT, **extra)  # type: ignore[arg-type]


def _event(action: str = "read_project_data") -> AuditEvent:
    return AuditEvent(CID, "domain.risk", action, ActionClass.READ, PROJECT, {"k": "v"})


# --- Politique -------------------------------------------------------------


def test_policy_file_covers_every_class() -> None:
    classes = {p.class_ for p in POLICY.actions.values()}
    assert classes == set(ActionClass)


def test_irreversible_action_cannot_be_automated() -> None:
    with pytest.raises(ValidationError, match="irréversible"):
        ActionPolicy.model_validate({"class": "irreversible", "level": "automation"})


def test_reviewed_action_needs_approvers() -> None:
    with pytest.raises(ValidationError, match="approbateurs"):
        ActionPolicy.model_validate({"class": "reversible_write", "level": "assistance"})


def test_reads_are_automated_for_any_agent() -> None:
    decision = decide(POLICY, _request("read_project_data"), Autonomy.AUGMENTATION, None)
    assert decision.verdict is Verdict.ALLOW


def test_agent_ceiling_restricts_an_automated_action() -> None:
    decision = decide(POLICY, _request("update_task_status"), Autonomy.ASSISTANCE, None)
    assert (decision.verdict, decision.level) == (Verdict.NEEDS_HUMAN, Autonomy.ASSISTANCE)


def test_unknown_action_is_denied() -> None:
    assert (
        decide(POLICY, _request("format_disk"), Autonomy.AUTOMATION, None).verdict is Verdict.DENY
    )


def test_approval_from_the_right_role_allows() -> None:
    approval = Approval("Zakaria Belmeddah", "pmo")
    decision = decide(POLICY, _request("close_project"), Autonomy.AUTOMATION, approval)
    assert decision.verdict is Verdict.ALLOW
    assert "Zakaria Belmeddah" in decision.reason


def test_allowlisted_subdomain_is_accepted() -> None:
    request = _request("read_project_data", destination="https://api.openrouter.ai/v1")
    assert decide(POLICY, request, Autonomy.AUTOMATION, None).verdict is Verdict.ALLOW


# --- Journal d'audit -------------------------------------------------------


def test_audit_chain_verifies() -> None:
    audit = make_audit()
    for _ in range(3):
        audit.append(_event())
    report = audit.verify()
    assert report.ok and report.entries == 3


def test_audit_refuses_update_and_delete() -> None:
    sessions = audit_sessions()
    make_audit(sessions).append(_event())
    for statement in ("UPDATE agent_log SET agent = 'pirate'", "DELETE FROM agent_log"):
        with pytest.raises(DatabaseError, match="ajout seul"), sessions.begin() as session:
            session.execute(text(statement))


def test_tampering_is_detected() -> None:
    sessions = audit_sessions()
    audit = make_audit(sessions)
    audit.append(_event())
    audit.append(_event())
    with sessions.begin() as session:
        session.execute(text("DROP TRIGGER agent_log_no_update"))
        session.execute(text("UPDATE agent_log SET agent = 'pirate' WHERE id = 1"))
    report = audit.verify()
    assert (report.first_broken_id, report.reason) == (1, "contenu modifié")


def test_wrong_key_is_detected() -> None:
    sessions = audit_sessions()
    make_audit(sessions).append(_event())
    assert make_audit(sessions).verify().reason == "signature invalide"


def test_audit_without_key_fails_closed() -> None:
    audit = AuditLog(audit_sessions(), InMemorySecretStore())
    with pytest.raises(MissingSigningKeyError):
        audit.append(_event())


# --- Portail ---------------------------------------------------------------


def test_every_decision_is_logged_before_effect() -> None:
    audit = make_audit()
    gate = make_gate(audit)
    result = gate.act(_request("read_project_data"), lambda: "ok", CID)
    assert (result.executed, result.value) == (True, "ok")
    assert audit.verify().entries == 1


def test_no_effect_without_audit_entry() -> None:
    gate = make_gate(AuditLog(audit_sessions(), InMemorySecretStore()))
    effects: list[str] = []
    with pytest.raises(MissingSigningKeyError):
        gate.act(_request("read_project_data"), lambda: effects.append("x"), CID)
    assert effects == []


def test_read_channel_refuses_writes() -> None:
    with pytest.raises(NotAReadError):
        make_gate().read(_request("update_task_status"), lambda: None, CID)


def test_failed_handler_is_logged() -> None:
    audit = make_audit()

    def boom() -> None:
        raise RuntimeError("panne")

    with pytest.raises(RuntimeError):
        make_gate(audit).act(_request("read_project_data"), boom, CID)
    assert audit.verify().entries == 2


def test_unknown_agent_is_denied() -> None:
    result = make_gate().act(_request("read_project_data", agent="intrus"), lambda: None, CID)
    assert result.decision.verdict is Verdict.DENY


def test_every_catalog_agent_has_a_ceiling() -> None:
    assert all(agent.autonomy in Autonomy for agent in CATALOG.all_agents())
