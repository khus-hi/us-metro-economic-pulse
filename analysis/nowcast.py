"""Next-month unemployment-rate nowcast per metro, tested against naive baselines.

Target: a metro's unemployment rate next month (BLS LAUS, not seasonally
adjusted), which BLS publishes about a month after the national figure.

Baselines:
- naive_last: next month = this month. Ignores seasonality.
- seasonal_naive: next month = same month last year + this month's YoY change.
  It keeps the seasonal shape and assumes the current trend persists.

Model (ridge regression, one model pooled across all 50 metros):
  predicts the YoY change of next month's rate from information known now:
  this month's and last month's YoY change, job growth and its 3-month
  change, and the national unemployment rate's YoY change (released earlier
  than metro data). Prediction = same month last year + predicted YoY change.
  The seasonal naive is the special case "coefficient 1 on this month's YoY
  change, 0 on everything else", so the model can only win by learning
  something real.

Validation: expanding-window time-series CV. Each fold trains on every target
month before the fold and forecasts the fold's 12 months one step ahead, so
the model never sees the future. Reported: MAPE (what was asked) and MAE in
percentage points (easier to read for a rate).

Data gap: BLS published no October 2025 metro unemployment rates (federal
government shutdown). October 2025 is never used as a target. Where it is
needed as a lag, it is linearly interpolated from Sep and Nov 2025 and the
row is flagged `uses_imputed_lag`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

FEATURES = ["u_yoy", "u_yoy_lag1", "job_growth", "job_growth_change_3m", "us_u_yoy"]


def build_panel(monthly: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for cbsa, g in monthly.groupby("cbsa_code"):
        g = g.set_index("month_date").sort_index()
        idx = pd.date_range(g.index.min(), g.index.max(), freq="MS")
        g = g.reindex(idx)
        g["cbsa_code"] = cbsa
        g["u_reported"] = g["unemployment_rate"]
        g["u"] = g["unemployment_rate"].interpolate(limit=1, limit_area="inside")
        g["u_imputed"] = g["u_reported"].isna() & g["u"].notna()
        g["us_u"] = g["us_unemployment_rate"].interpolate(limit=1, limit_area="inside")
        g["jobs_yoy"] = g["nonfarm_jobs_yoy_pct"]
        frames.append(g)
    p = pd.concat(frames).rename_axis("month_date").reset_index()
    s = p.groupby("cbsa_code")

    p["u_lag1"] = s["u"].shift(1)
    p["u_lag11"] = s["u"].shift(11)    # same calendar month as the target, a year earlier
    p["u_lag12"] = s["u"].shift(12)
    p["u_lag13"] = s["u"].shift(13)
    p["u_yoy"] = p["u"] - p["u_lag12"]
    p["u_yoy_lag1"] = p["u_lag1"] - p["u_lag13"]
    p["job_growth"] = p["jobs_yoy"]
    p["job_growth_change_3m"] = p["jobs_yoy"] - s["jobs_yoy"].shift(3)
    p["us_u_yoy"] = p["us_u"] - s["us_u"].shift(12)

    p["target_month"] = p["month_date"] + pd.DateOffset(months=1)
    p["u_next"] = s["u_reported"].shift(-1)          # only real, published values as targets
    p["y"] = p["u_next"] - p["u_lag11"]
    lag_imputed = [s["u_imputed"].shift(k).fillna(False).astype(bool) for k in (0, 1, 11, 12, 13)]
    p["uses_imputed_lag"] = np.logical_or.reduce(lag_imputed)

    p["pred_naive_last"] = p["u"]
    p["pred_seasonal_naive"] = p["u_lag11"] + p["u_yoy"]
    return p


def _model(alpha: float):
    return make_pipeline(StandardScaler(), Ridge(alpha=alpha))


def _train_mask(p: pd.DataFrame, cfg: dict) -> pd.Series:
    ex = cfg.get("exclude_from_training") or {}
    m = p[FEATURES + ["y", "u_lag11"]].notna().all(axis=1)
    if ex:
        m &= ~p["target_month"].between(pd.Timestamp(ex["start"]), pd.Timestamp(ex["end"]))
    return m


def mape(actual, pred) -> float:
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    return float(np.mean(np.abs(actual - pred) / np.abs(actual)) * 100)


def cross_validate(p: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    usable = p[FEATURES + ["y", "u_lag11"]].notna().all(axis=1)
    last_target = p.loc[usable, "target_month"].max()
    n, k = cfg.get("n_folds", 4), cfg.get("fold_months", 12)
    train_ok = _train_mask(p, cfg)
    preds, rows = [], []
    for i in range(n, 0, -1):
        start = last_target - pd.DateOffset(months=i * k - 1)
        end = start + pd.DateOffset(months=k - 1)
        test = usable & p["target_month"].between(start, end)
        train = train_ok & (p["target_month"] < start)
        model = _model(cfg.get("alpha", 1.0)).fit(p.loc[train, FEATURES], p.loc[train, "y"])
        t = p.loc[test, ["cbsa_code", "month_date", "target_month", "u_next",
                         "pred_naive_last", "pred_seasonal_naive", "u_lag11"]].copy()
        t["pred_model"] = t["u_lag11"] + model.predict(p.loc[test, FEATURES])
        t["fold"] = f"{start:%Y-%m}..{end:%Y-%m}"
        preds.append(t)
        row = {"fold": t["fold"].iloc[0], "train_rows": int(train.sum()), "test_rows": int(test.sum())}
        for name in ("model", "seasonal_naive", "naive_last"):
            row[f"mape_{name}"] = mape(t["u_next"], t[f"pred_{name}"])
            row[f"mae_pp_{name}"] = float(np.mean(np.abs(t["u_next"] - t[f"pred_{name}"])))
        rows.append(row)
    all_preds = pd.concat(preds)
    overall = {"fold": "all folds", "train_rows": np.nan, "test_rows": len(all_preds)}
    for name in ("model", "seasonal_naive", "naive_last"):
        overall[f"mape_{name}"] = mape(all_preds["u_next"], all_preds[f"pred_{name}"])
        overall[f"mae_pp_{name}"] = float(np.mean(np.abs(all_preds["u_next"] - all_preds[f"pred_{name}"])))
    return pd.DataFrame(rows + [overall]), all_preds


def nowcast_next(p: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    """Fit on everything usable, forecast the month after the latest data."""
    train = _train_mask(p, cfg)
    model = _model(cfg.get("alpha", 1.0)).fit(p.loc[train, FEATURES], p.loc[train, "y"])
    latest = p.dropna(subset=["u_reported"])["month_date"].max()
    now = p[(p["month_date"] == latest)].dropna(subset=FEATURES + ["u_lag11"]).copy()
    now["nowcast"] = now["u_lag11"] + model.predict(now[FEATURES])
    out = now[["cbsa_code", "month_date", "target_month", "u", "u_lag11", "nowcast",
               "pred_seasonal_naive", "pred_naive_last", "uses_imputed_lag"]].rename(columns={
        "month_date": "latest_month", "u": "latest_rate", "u_lag11": "same_month_last_year"})
    out["nowcast_change_pp"] = out["nowcast"] - out["latest_rate"]
    out["nowcast_yoy_pp"] = out["nowcast"] - out["same_month_last_year"]
    coefs = dict(zip(FEATURES, model[-1].coef_ / model[0].scale_))
    return out.sort_values("cbsa_code").reset_index(drop=True), coefs
