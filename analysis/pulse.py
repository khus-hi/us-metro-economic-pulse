"""Composite 'pulse' index per metro per month.

Method (interview version):
1. Four components, each oriented so higher = stronger economy:
   job growth (YoY %), minus the unemployment-rate change (YoY pp), real wage
   growth (pp), and job openings.
2. Standardise each component *across metros within a month* (z-score). That
   puts percent and percentage-point measures on one scale and makes the index
   relative: 0 = the average top-50 metro that month, +1 = one standard
   deviation stronger.
3. Weighted average of the z-scores. If a metro lacks a component that month
   (bimonthly CPI, stale JOLTS), the remaining weights are re-normalised and
   `components_used` records what went in.
4. Acceleration = change in the pulse over N months: a metro moving up
   relative to the others.

Why YoY changes and not month-over-month? Metro LAUS rates and most CES
metro series are not seasonally adjusted; comparing with the same month a year
earlier removes the seasonal pattern without a model.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# component -> (column, sign). Sign -1 means "lower is better".
COMPONENTS = {
    "job_growth": ("nonfarm_jobs_yoy_pct", 1),
    "unemployment_change": ("unemployment_change_yoy_pp", -1),
    "real_wage_growth": ("real_wage_growth_pp", 1),
    "openings": ("openings", 1),
}
KEY = ["cbsa_code", "month_date"]


def _shift_months(df: pd.DataFrame, col: str, months: int, name: str) -> pd.DataFrame:
    """Join the value from `months` months earlier (by date, not row position,
    so a missing month never silently shifts the comparison)."""
    prev = df[KEY + [col]].copy()
    prev["month_date"] = prev["month_date"] + pd.DateOffset(months=months)
    return df.merge(prev.rename(columns={col: name}), on=KEY, how="left")


def prepare(monthly: pd.DataFrame, cfg: dict, postings: pd.DataFrame | None = None) -> pd.DataFrame:
    df = monthly.sort_values(KEY).copy()
    df = _shift_months(df, "unemployment_rate", 12, "unemployment_rate_12m_ago")
    df["unemployment_change_yoy_pp"] = df["unemployment_rate"] - df["unemployment_rate_12m_ago"]

    # 29 metros use bimonthly CPI, so real wage growth exists every other month.
    # Carry the last value forward one month at most, and flag it.
    df["real_wage_growth_pp"] = df.groupby("cbsa_code")["real_wage_growth_pct"].ffill(limit=1)
    df["real_wage_is_carried"] = df["real_wage_growth_pct"].isna() & df["real_wage_growth_pp"].notna()

    source = cfg.get("openings_source", "jolts_state")
    if source == "jolts_state":
        has = df["state_job_openings_rate"].notna()
        df["openings_month"] = df["month_date"].where(has)
        df["openings_month"] = df.groupby("cbsa_code")["openings_month"].ffill()
        df["openings"] = df.groupby("cbsa_code")["state_job_openings_rate"].ffill()
        age = (df["month_date"].dt.year - df["openings_month"].dt.year) * 12 + \
              (df["month_date"].dt.month - df["openings_month"].dt.month)
        df.loc[age > cfg.get("openings_max_age_months", 12), "openings"] = np.nan
    elif source == "postings":
        if postings is None:
            raise ValueError("openings_source=postings needs fct_postings")
        open_now = postings[postings["is_open"].astype(str).str.lower() == "true"]
        counts = open_now.dropna(subset=["cbsa_code"]).groupby("cbsa_code")["job_key"].nunique()
        latest = df["month_date"].max()
        jobs = df[df["month_date"] == latest].set_index("cbsa_code")["nonfarm_jobs_thousands"]
        per_100k = (counts.reindex(jobs.index).fillna(0) / (jobs * 1000) * 1e5)
        df["openings"] = np.nan
        mask = df["month_date"] == latest
        df.loc[mask, "openings"] = df.loc[mask, "cbsa_code"].map(per_100k)
        df["openings_month"] = df["month_date"].where(mask)
    else:
        raise ValueError(f"unknown openings_source {source!r}")
    return df


def zscore_within_month(df: pd.DataFrame, col: str, min_n: int) -> pd.Series:
    g = df.groupby("month_date")[col]
    z = (df[col] - g.transform("mean")) / g.transform(lambda s: s.std(ddof=0))
    return z.where(g.transform("count") >= min_n)


def compute(monthly: pd.DataFrame, cfg: dict, postings: pd.DataFrame | None = None) -> pd.DataFrame:
    weights = {k: float(v) for k, v in cfg["weights"].items() if float(v) > 0}
    unknown = set(weights) - set(COMPONENTS)
    if unknown:
        raise ValueError(f"unknown pulse components {unknown}; choose from {list(COMPONENTS)}")
    df = prepare(monthly, cfg, postings)
    min_n = cfg.get("min_metros_per_month", 40)

    num = pd.Series(0.0, index=df.index)
    den = pd.Series(0.0, index=df.index)
    used = pd.Series("", index=df.index)
    for comp, w in weights.items():
        col, sign = COMPONENTS[comp]
        z = sign * zscore_within_month(df, col, min_n)
        df[f"z_{comp}"] = z
        present = z.notna()
        num[present] += w * z[present]
        den[present] += w
        used[present] += comp + ";"
    # Require the two monthly-everywhere components; otherwise no index that month.
    core = df["z_job_growth"].notna() if "job_growth" in weights else True
    core &= df["z_unemployment_change"].notna() if "unemployment_change" in weights else True
    df["pulse"] = (num / den.replace(0, np.nan)).where(core)
    df["weight_coverage"] = den / sum(weights.values())
    df["components_used"] = used.str.rstrip(";")
    df["pulse_rank"] = df.groupby("month_date")["pulse"].rank(ascending=False, method="min")

    n = cfg.get("acceleration_months", 3)
    df = _shift_months(df, "pulse", n, f"pulse_{n}m_ago")
    df[f"pulse_change_{n}m"] = df["pulse"] - df[f"pulse_{n}m_ago"]
    df = _shift_months(df, "nonfarm_jobs_yoy_pct", n, f"job_growth_{n}m_ago")
    df[f"job_growth_change_{n}m_pp"] = df["nonfarm_jobs_yoy_pct"] - df[f"job_growth_{n}m_ago"]
    return df


def latest_month(df: pd.DataFrame) -> pd.Timestamp:
    counts = df.dropna(subset=["pulse"]).groupby("month_date").size()
    return counts.index.max()
