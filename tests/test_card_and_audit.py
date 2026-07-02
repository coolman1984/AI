import pytest

from engines.audit.audit import approve_report, audit_card
from engines.data.clean import clean_actuals
from engines.data.drivers import run_variance_decomposition
from engines.data.ingest import get_connection, ingest_csv
from engines.data.variance import material_cost_variance
from serving.card import compute_data_quality, make_manager_card

AUDIT_CFG = {"recompute_tolerance": 0.01, "certainty_release_threshold": 0.80,
             "materiality_warn_ratio": 0.02}


def _build():
    con = get_connection()
    rows_in = ingest_csv(con, "ra", "data/sample/finance_actuals.csv")
    ingest_csv(con, "rb", "data/sample/finance_budget.csv")
    budget = con.execute("SELECT sub_assembly, budget_amount FROM rb").pl()
    clean, rejects, _ = clean_actuals(con, "ra")
    bridge = material_cost_variance(clean, budget)
    decomp = run_variance_decomposition(
        "data/sample/finance_actuals.csv", "data/sample/finance_standards.csv", {"audit": AUDIT_CFG}
    )["decomposition"]
    dq = compute_data_quality(rows_in, rejects, bridge.total_actual, AUDIT_CFG)
    card = make_manager_card(bridge, dq, decomposition=decomp)
    return rows_in, clean, rejects, budget, bridge, decomp, card


def test_card_refuses_number_without_evidence():
    *_, card = _build()
    card.validate()  # ok
    card.key_numbers[0].evidence = None
    with pytest.raises(ValueError):
        card.validate()


def test_card_includes_driver_split_when_available():
    *_, decomp, card = _build()
    assert card.driver_split is not None
    assert round(card.driver_split.total.value, 2) == round(decomp.total, 2)
    assert len(card.key_numbers) == 2


def test_audit_independent_recompute_matches():
    rows_in, clean, rejects, budget, bridge, decomp, card = _build()
    res = audit_card(card, bridge, decomp, clean, budget, rows_in, len(rejects), AUDIT_CFG)
    assert res.passed is True
    assert abs(res.recomputed["variance"] - bridge.total_variance) < 0.01
    assert 0.0 <= res.certainty["overall"] <= 1.0


def test_audit_flags_a_tampered_total():
    rows_in, clean, rejects, budget, bridge, decomp, card = _build()
    bridge.total_actual += 999.0  # someone tampers with the number
    res = audit_card(card, bridge, decomp, clean, budget, rows_in, len(rejects), AUDIT_CFG)
    assert res.passed is False
    assert any("mismatch" in i for i in res.issues)


def test_audit_flags_a_tampered_driver_split():
    rows_in, clean, rejects, budget, bridge, decomp, card = _build()
    assert card.driver_split is not None
    card.driver_split.price.value += 10.0
    res = audit_card(card, bridge, decomp, clean, budget, rows_in, len(rejects), AUDIT_CFG)
    assert res.passed is False
    assert any("driver view does not match" in i for i in res.issues)


def test_low_quality_triggers_human_question_and_blocks_unsigned():
    rows_in, clean, rejects, budget, bridge, decomp, card = _build()
    res = audit_card(card, bridge, decomp, clean, budget, rows_in, len(rejects), AUDIT_CFG)
    # sample has 3/8 rejects -> low data quality -> must ask the human
    assert res.needs_human is True
    assert len(res.questions) >= 1
    so = approve_report(res, "analyst_mohamed")
    assert so.approved is True  # numbers are sound; human accepts responsibility
