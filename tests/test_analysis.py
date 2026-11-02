"""Logic tests for analysis/. Tiny hand-made inputs, not data."""
import pandas as pd
import pytest

from analysis import nowcast, pulse
from analysis.__main__ import parse_weights


def test_mape():
    assert nowcast.mape([4.0, 5.0], [4.4, 4.5]) == pytest.approx(10.0)


def test_parse_weights():
    assert parse_weights("job_growth=0.5, openings=0") == {"job_growth": 0.5, "openings": 0.0}


def _monthly(rows):
    df = pd.DataFrame(rows, columns=["cbsa_code", "month_date", "unemployment_rate", "nonfarm_jobs_yoy_pct",
                                     "real_wage_growth_pct", "state_job_openings_rate"])
    df["month_date"] = pd.to_datetime(df["month_date"])
    return df


def test_pulse_standardises_within_month_and_renormalises_weights():
    rows = []
    for code, jg, u0, u1 in (("A", 3.0, 4.0, 3.0), ("B", 1.0, 4.0, 4.0), ("C", 2.0, 4.0, 5.0)):
        rows.append([code, "2025-01-01", u0, None, None, None])
        rows.append([code, "2026-01-01", u1, jg, None, None])   # no wage or openings data
    cfg = {"weights": {"job_growth": 1, "unemployment_change": 1, "real_wage_growth": 1, "openings": 1},
           "min_metros_per_month": 3, "acceleration_months": 3}
    out = pulse.compute(_monthly(rows), cfg)
    jan = out[out["month_date"] == "2026-01-01"].set_index("cbsa_code")
    # z(job growth) = [+1.22, -1.22, 0]; -z(unemp. change) = [+1.22, 0, -1.22]
    assert jan.loc["A", "pulse"] == pytest.approx(1.2247, abs=1e-3)
    assert jan.loc["A", "components_used"] == "job_growth;unemployment_change"
    assert jan.loc["A", "weight_coverage"] == pytest.approx(0.5)
    assert jan["pulse_rank"].to_dict() == {"A": 1, "B": 2, "C": 2}


def test_openings_dropped_when_too_old():
    rows = [["A", "2025-01-01", 4, 1, None, 5.0], ["A", "2026-06-01", 4, 1, None, None]]
    df = pulse.prepare(_monthly(rows), {"openings_source": "jolts_state", "openings_max_age_months": 12})
    assert df.set_index("month_date").loc["2026-06-01", "openings"] != df.set_index("month_date").loc["2026-06-01", "openings"]  # NaN


def test_seasonal_naive_and_gap_interpolation():
    months = pd.date_range("2024-01-01", "2025-03-01", freq="MS")
    u = [4.0 + 0.1 * i for i in range(len(months))]
    df = pd.DataFrame({"cbsa_code": "A", "month_date": months, "unemployment_rate": u,
                       "us_unemployment_rate": 4.0, "nonfarm_jobs_yoy_pct": 1.0})
    df.loc[df["month_date"] == "2024-06-01", "unemployment_rate"] = None   # a missing month
    p = nowcast.build_panel(df).set_index("month_date")
    assert bool(p.loc["2024-06-01", "u_imputed"])
    assert p.loc["2024-06-01", "u"] == pytest.approx(4.5)
    assert pd.isna(p.loc["2024-05-01", "u_next"])           # an imputed month is never a target
    r = p.loc["2025-01-01"]                                    # forecasting Feb 2025
    assert r["pred_seasonal_naive"] == pytest.approx(r["u_lag11"] + (r["u"] - r["u_lag12"]))
