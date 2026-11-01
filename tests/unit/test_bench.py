"""Notation du benchmark et exécution à blanc (modèle factice)."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from bench import run
from bench.tasks import TASKS, extract_json

from boussole.agents.catalog import load_catalog
from boussole.platform.llm_gateway.openrouter import OpenRouterGateway
from tests.contract import simulated_openrouter

TASK = {t.name: t for t in TASKS}


def test_datasets_match_the_phase_0_brief() -> None:
    assert len(TASK["approach"].items()) == 10
    assert {i["expected"] for i in TASK["approach"].items()} == {"predictive", "adaptive", "hybrid"}
    assert all(len(TASK[n].items()) >= 5 for n in ("status", "risks"))


def test_extract_json_tolerates_code_fences() -> None:
    assert extract_json('Voici :\n```json\n{"approche": "hybrid"}\n```') == {"approche": "hybrid"}
    assert extract_json("pas de json") is None


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ('{"approche": "Hybride", "justification": "x"}', 1.0),
        ('{"approche": "predictive"}', 0.0),
        ("hybride", 0.0),
    ],
)
def test_approach_scoring(answer: str, expected: float) -> None:
    item = next(i for i in TASK["approach"].items() if i["expected"] == "hybrid")
    assert TASK["approach"].score(item, answer) == expected


def test_risk_scoring_rewards_recall_and_valid_scores() -> None:
    item = TASK["risks"].items()[1]  # pluie, acier, inspecteur
    good = [
        {"titre": "Pluie pendant les fondations", "probabilite": 4, "impact": 3},
        {"titre": "Hausse du prix de l'acier", "probabilite": 5, "impact": 4},
        {"titre": "Visite de l'inspecteur non confirmée", "probabilite": 3, "impact": 4},
    ]
    assert TASK["risks"].score(item, json.dumps(good, ensure_ascii=False)) == 1.0
    bad_scale = [{**good[0], "probabilite": 9}]
    assert TASK["risks"].score(item, json.dumps(bad_scale)) == pytest.approx(1 / 3 * 0.5)
    assert TASK["risks"].score(item, "aucun risque") == 0.0


def test_status_scoring_penalises_long_answers() -> None:
    item = TASK["status"].items()[0]
    short = (
        "Budget : 410 k$ sur 500 k$. Retard de 3 semaines (fournisseur, extraction). "
        "Décision : portée des rapports."
    )
    assert TASK["status"].score(item, short) == 1.0
    assert TASK["status"].score(item, short + " mot" * 200) == 0.5


def test_recommend_prefers_cheaper_model_when_close() -> None:
    summary = {
        "cher": {"global": 0.90, "cost_cad": 0.50},
        "abordable": {"global": 0.87, "cost_cad": 0.05},
        "faible": {"global": 0.60, "cost_cad": 0.01},
    }
    assert run.recommend(summary) == "abordable"


def test_estimate_uses_openrouter_prices_in_cad() -> None:
    gateway = OpenRouterGateway(
        "sk-or-test", Decimal("1.40"), transport=simulated_openrouter.transport()
    )
    catalog = load_catalog(Path(__file__).resolve().parents[2] / "config" / "agents.yaml")
    estimates = run.estimate_cost_cad(gateway, catalog, ["anthropic/claude-sonnet-5.5"])
    assert Decimal("0") < estimates["anthropic/claude-sonnet-5.5"] < Decimal("1")


def test_dry_run_writes_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    assert run.main(["--dry-run"]) == 0
    (result,) = tmp_path.glob("*-dry-run.json")
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert set(payload["summary"]) == {"fake/small", "fake/large"}
    assert len(payload["rows"]) == 2 * sum(len(t.items()) for t in TASKS)


def test_truncated_or_empty_answers_are_errors_not_zeros() -> None:
    from boussole.platform.llm_gateway.port import GenerationResult, Usage

    usage = Usage(1, 1, Decimal("0"))
    truncated = GenerationResult('{"approche": "hyb', "m", usage, finish_reason="length")
    empty = GenerationResult("", "m", usage, finish_reason="stop")
    assert "tronquée" in (run._answer_problem(truncated) or "")
    assert "vide" in (run._answer_problem(empty) or "")
    assert run._answer_problem(GenerationResult("ok", "m", usage, finish_reason="stop")) is None


def test_network_failures_are_retried_then_stop_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("time.sleep", lambda _: None)
    down = run.Row("m", "status", "s01", 0.0, "0", 0.0, "", "OpenRouter injoignable : ConnectError")
    up = run.Row("m", "status", "s01", 1.0, "0", 0.0, "ok", None)
    attempts = iter([down, down, up])
    assert run._with_retries(lambda: next(attempts)) == up
    monkeypatch.setattr(run, "_run_item", lambda *args: down)
    with pytest.raises(run.NetworkDownError):
        catalog = load_catalog(Path(__file__).resolve().parents[2] / "config" / "agents.yaml")
        run.run_model(None, catalog, "m")  # type: ignore[arg-type]


def test_hard_suite_covers_the_three_tasks_and_all_approaches() -> None:
    assert all(len(TASK[n].items("hard")) >= 5 for n in ("status", "risks", "approach"))
    assert {i["expected"] for i in TASK["approach"].items("hard")} == {
        "predictive",
        "adaptive",
        "hybrid",
    }


def test_status_prompt_announces_the_word_limit() -> None:
    item = TASK["status"].items("hard")[0]
    assert "150 mots" in TASK["status"].prompt(item)


def test_hard_status_rewards_flagging_the_contradiction() -> None:
    item = TASK["status"].items("hard")[0]  # tableau de bord « respecté » contre 1,32 M$
    facts = (
        "Budget : 1,32 M$ engagés sur 1,1 M$. 41 anomalies bloquantes. "
        "Mise en service 1er février. Décision : réserve de 150 000 $."
    )
    flagged = facts + " Incohérence : le tableau de bord dit « respecté »."
    assert TASK["status"].score(item, flagged) == 1.0
    assert TASK["status"].score(item, facts) == pytest.approx(0.8)


def test_dry_run_on_the_hard_suite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(run, "RESULTS", tmp_path)
    assert run.main(["--dry-run", "--suite", "hard"]) == 0
    (result,) = tmp_path.glob("*-dry-run.json")
    payload = json.loads(result.read_text(encoding="utf-8"))
    assert payload["suite"] == "hard"
    assert len(payload["rows"]) == 2 * sum(len(t.items("hard")) for t in TASKS)
