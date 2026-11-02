"""Build the report-ready tables the dashboard connects to (dashboard/data/report/).

One table per need, each already carrying metro names and labels, so the
dashboard never has to blend or join (Looker Studio blends are slow and
limited; Power BI could relate them, but flat tables keep both tools simple).

Run after `python -m analysis run`:
    python dashboard/report_tables.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
MARTS = ROOT / "dashboard" / "data"
ANALYSIS = ROOT / "analysis" / "output"
OUT = MARTS / "report"
S = {"cbsa_code": str, "soc_code": str}
LOCATION_LABELS = {"remote_us": "Remote (US)", "non_us": "Outside the US",
                   "us_unmapped": "US, outside top 50", "unknown": "Location unclear"}


def metros() -> pd.DataFrame:
    d = pd.read_csv(MARTS / "dim_metro.csv", dtype=S)
    d["metro"] = d["short_name"].str.strip()
    return d[["cbsa_code", "metro", "cbsa_title", "principal_state", "census_region", "population",
              "pop_rank", "cpi_geo_level"]]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    dim = metros()
    names = dim[["cbsa_code", "metro", "principal_state", "census_region"]]
    written = {}

    # 1. Metro ranking (latest month, one row per metro)
    latest = pd.read_csv(ANALYSIS / "pulse_latest.csv", dtype=S)
    pm = pd.read_csv(ANALYSIS / "pulse_monthly.csv", dtype=S, parse_dates=["month_date"])
    m = latest["month_date"].iloc[0]
    prev = pm[pm["month_date"] == pd.Timestamp(m) - pd.DateOffset(months=3)][["cbsa_code", "pulse_rank"]]
    r = latest.merge(prev.rename(columns={"pulse_rank": "pulse_rank_3m_ago"}), on="cbsa_code", how="left")
    r["rank_change_3m"] = r["pulse_rank_3m_ago"] - r["pulse_rank"]   # positive = moved up
    written["metro_ranking"] = dim.merge(r, on="cbsa_code")

    # 2. Metro monthly history (deep dive); pulse joined onto the full indicator set
    mm = pd.read_csv(MARTS / "fct_metro_monthly.csv", dtype=S, parse_dates=["month_date"])
    mm = mm[mm["month_date"] >= "2016-01-01"]
    keep = ["cbsa_code", "month_date", "unemployment_rate", "us_unemployment_rate", "nonfarm_jobs_thousands",
            "nonfarm_jobs_yoy_pct", "avg_hourly_earnings", "avg_hourly_earnings_yoy_pct", "cpi_yoy_pct",
            "us_cpi_yoy_pct", "real_wage_growth_pct", "state_job_openings_rate", "laus_is_preliminary"]
    hist = mm[keep].merge(pm[["cbsa_code", "month_date", "pulse", "pulse_rank"]], on=["cbsa_code", "month_date"], how="left")
    written["metro_monthly"] = names.merge(hist, on="cbsa_code")

    # 3. Metro annual context (deep dive)
    written["metro_annual"] = names.merge(pd.read_csv(MARTS / "fct_metro_annual.csv", dtype=S), on="cbsa_code")

    # 4. Analyst pay
    written["analyst_pay"] = names.merge(pd.read_csv(MARTS / "fct_analyst_pay.csv", dtype=S), on="cbsa_code")

    # 5-6. Analyst demand: postings and tools, with a readable location label and the
    # metro's latest job count so the dashboard can show postings per 100k jobs.
    jobs = mm[mm["month_date"] == mm["month_date"].max()][["cbsa_code", "nonfarm_jobs_thousands"]]
    for table, src in (("analyst_postings", "fct_postings"), ("analyst_tools", "fct_posting_tools")):
        p = pd.read_csv(MARTS / f"{src}.csv", dtype=S).merge(names, on="cbsa_code", how="left")
        p["location_label"] = p["metro"].fillna(p["location_class"].map(LOCATION_LABELS))
        written[table] = p.merge(jobs.rename(columns={"nonfarm_jobs_thousands": "metro_jobs_thousands"}),
                                 on="cbsa_code", how="left")

    # 7. Nowcast backtest: every out-of-sample forecast, long format (one row per method)
    cv = pd.read_csv(ANALYSIS / "nowcast_cv_predictions.csv", dtype=S, parse_dates=["target_month"])
    long = cv.melt(id_vars=["cbsa_code", "target_month", "fold", "u_next"],
                   value_vars=["pred_model", "pred_seasonal_naive", "pred_naive_last"],
                   var_name="method", value_name="forecast")
    long["method"] = long["method"].map({"pred_model": "Ridge model", "pred_seasonal_naive": "Seasonal naive",
                                         "pred_naive_last": "Last value"})
    long = long.rename(columns={"u_next": "actual"})
    long["abs_error_pp"] = (long["forecast"] - long["actual"]).abs()
    long["abs_pct_error"] = long["abs_error_pp"] / long["actual"] * 100
    written["nowcast_backtest"] = names.merge(long, on="cbsa_code")

    # 8. Next-month nowcast
    written["nowcast_next"] = names.merge(pd.read_csv(ANALYSIS / "nowcast_next_month.csv", dtype=S), on="cbsa_code")

    for name, df in written.items():
        df.to_csv(OUT / f"{name}.csv", index=False, float_format="%.4f")
        print(f"{name:<18} {len(df):>7} rows  {(OUT / f'{name}.csv').stat().st_size / 1e6:5.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
