from datetime import date

import numpy as np
import pytest

from opsintel import config, db
from opsintel.ai.assistant import RulesEngine, ask
from opsintel.analytics import forecast
from opsintel.analytics.risk import InsufficientData


def test_trend_series_beats_naive_baseline():
    rng = np.random.default_rng(0)
    y = 100 + 8 * np.arange(18) + rng.normal(0, 2, 18)
    r = forecast.forecast_series(y)
    assert r["method"] == "holt" and r["mae"] < r["naive_mae"]
    assert r["point"][0] == pytest.approx(100 + 8 * 18, rel=0.05)
    assert all(lo <= p <= hi for lo, p, hi in zip(r["low"], r["point"], r["high"]))


def test_selected_method_never_worse_than_naive_in_backtest():
    y = np.random.default_rng(1).poisson(50, 18)
    r = forecast.forecast_series(y)
    assert r["mae"] <= r["naive_mae"] and (r["point"] >= 0).all()


def test_incident_forecast_matches_history():
    r = forecast.incident_forecast("category")
    assert r["last_complete_month"] == "2026-09" and r["forecast_months"] == ["2026-10", "2026-11", "2026-12"]
    sept = db.query_df("SELECT COUNT(*) AS n FROM incidents WHERE opened_month = '2026-09'").n[0]
    total = next(g for g in r["groups"] if g["group"] == "Total")
    assert total["last_month_actual"] == sept
    assert sum(v for k, v in r["history"][-1].items() if k != "month") == sept
    assert len(r["data"]) == 3 * len(r["groups"])


def test_cost_forecast_total_matches_ledger():
    r = forecast.cost_forecast()
    sept = db.query_df("SELECT SUM(amount_gbp) AS v FROM costs WHERE month = '2026-09'").v[0]
    assert r["groups"][0]["last_month_actual"] == pytest.approx(sept, abs=1)


def test_short_history_raises(monkeypatch):
    monkeypatch.setattr(config, "DATA_START", date(2026, 4, 1))
    with pytest.raises(InsufficientData, match="at least 9"):
        forecast.incident_forecast()


def test_assistant_forecast_is_grounded_and_role_checked():
    a = ask("How many incidents should we expect over the next three months by category?", "opsmgr.demo", engine=RulesEngine())
    assert not a.abstained and a.grounding["ungrounded"] == []
    assert [e.tool for e in a.evidence] == ["get_incident_forecast"]
    b = ask("Forecast our costs for next quarter", "desk.demo", engine=RulesEngine())
    assert b.abstained and "costs" in b.answer


def test_trim_skips_old_sparse_records_and_partial_first_month():
    import pandas as pd

    vals = [2, 0, 0, 0, 3, 0, 0, 0, 0, 48, 120, 110, 115]
    panel = pd.DataFrame({"Total": vals}, index=[f"m{i}" for i in range(len(vals))])
    assert forecast._trim(panel).Total.tolist() == [120, 110, 115]
