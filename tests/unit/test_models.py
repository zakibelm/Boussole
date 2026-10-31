"""Invariants du modèle de données, vérifiés sans base."""

from boussole.core.models import Base

PROJECT_SCOPED = {
    "deliverables",
    "resources",
    "tasks",
    "stakeholders",
    "risks",
    "budget_lines",
    "decisions",
}

FORBIDDEN_PERSONAL_COLUMNS = {"email", "phone", "address", "sentiment_text", "raw_text"}


def test_project_data_is_scoped_to_a_mandatory_project() -> None:
    for name in PROJECT_SCOPED:
        column = Base.metadata.tables[name].c.project_id
        assert not column.nullable, name


def test_stakeholders_minimise_personal_data() -> None:
    columns = set(Base.metadata.tables["stakeholders"].c.keys())
    assert columns.isdisjoint(FORBIDDEN_PERSONAL_COLUMNS)


def test_amounts_are_in_canadian_dollars() -> None:
    columns = Base.metadata.tables["budget_lines"].c.keys()
    money = [c for c in columns if c.startswith(("planned", "actual"))]
    assert money and all(c.endswith("_cad") for c in money)


def test_agent_log_is_chained_by_hash() -> None:
    columns = Base.metadata.tables["agent_log"].c
    assert {"correlation_id", "prev_hash", "entry_hash", "signature"} <= set(columns.keys())
    assert columns.entry_hash.unique


def test_knowledge_documents_never_store_content() -> None:
    columns = set(Base.metadata.tables["knowledge_documents"].c.keys())
    assert "content" not in columns
    assert "content_sha256" in columns
