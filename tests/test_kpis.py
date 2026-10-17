import pytest

from eval import ground_truth as gt
from opsintel.analytics import kpis, risk


def test_breach_rate_matches_independent_truth():
    r = kpis.sla_breach_rate("2026Q3", "category")
    by_cat = {d["category"]: d for d in r["data"]}
    for cat in ("Network", "Cloud", "End User"):
        assert by_cat[cat]["breach_rate_pct"] == gt.breach_rate("2026Q3", cat)
        assert by_cat[cat]["prev_breach_rate_pct"] == gt.breach_rate("2026Q2", cat)
    assert r["data"][0]["category"] == gt.top_breach_category("2026Q3")


def test_cost_change_matches_truth():
    r = kpis.cost_change("2026-09")
    assert r["total_current_gbp"] == pytest.approx(gt.cost_total("2026-09"), abs=0.01)
    svc, ctype, amt = gt.top_cost_driver("2026-09")
    assert (r["data"][0]["service"], r["data"][0]["cost_type"]) == (svc, ctype)
    assert r["data"][0]["change_gbp"] == pytest.approx(amt, abs=0.01)


def test_relative_periods_anchor_on_snapshot():
    assert kpis.resolve_period("last_quarter") == ("quarter", "2026Q3")
    assert kpis.resolve_period("previous_quarter") == ("quarter", "2026Q2")
    assert kpis.resolve_period("this_month") == ("month", "2026-09")
    assert kpis.resolve_period("q1 2026") == ("quarter", "2026Q1")


def test_out_of_coverage_period_raises():
    with pytest.raises(ValueError, match="No data"):
        kpis.sla_breach_rate("2023Q2")


def test_risk_model_beats_persistence_baseline():
    ev = risk.sla_risk_next_week()["evaluation"]
    assert ev["model_auc"] > ev["baseline_persistence_auc"]
    assert ev["model_brier"] < ev["baseline_persistence_brier"]


def test_risk_output_has_intervals_and_drivers():
    r = risk.sla_risk_next_week()
    for d in r["data"]:
        lo, hi = d["interval_pct"]
        assert 0 <= lo <= hi <= 100
    assert r["data"][0]["top_drivers"]


def test_delivery_risk_scores_overdue_first():
    d = risk.delivery_delay_risk(10)["data"]
    assert d[0]["overdue"] and d[0]["risk_score"] == 100
