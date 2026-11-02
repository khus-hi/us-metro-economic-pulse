# Analysis: pulse index, unemployment nowcast, findings

```bash
python -m analysis run                                   # reads dashboard/data/*.csv
python -m analysis run --weights job_growth=0.5,openings=0
python -m analysis run --openings-source postings
python -m analysis run --duckdb warehouse/pulse.duckdb   # read the live warehouse instead
```

Settings are in `analysis/config.yml`. The outputs go to `analysis/output/`:

| File | What it holds |
|---|---|
| `pulse_monthly.csv` | The pulse index for every metro and month, with each component's z-score. |
| `pulse_latest.csv` | The latest month only. |
| `nowcast_cv.csv` | Accuracy for each validation fold, for the model and both naive baselines. |
| `nowcast_cv_predictions.csv` | Every forecast made during validation. |
| `nowcast_next_month.csv` | Next month's unemployment rate per metro: the model's forecast plus both baselines. |
| `findings.md` / `findings.json` | The findings. Every number in them is computed by `analysis/findings.py`; none is typed by hand. |

The analysis reads the committed mart CSVs, so anyone with a fresh clone can reproduce it without API keys or a warehouse. GitHub Actions re-runs it every month after the marts refresh.

## Pulse index

The index combines four components. Each is turned around if needed so that higher always means stronger.

| Component | Source | Direction |
|---|---|---|
| Job growth | BLS CES, % change in nonfarm jobs vs the same month last year | higher is better |
| Unemployment change | BLS LAUS, change in the unemployment rate vs a year ago (pp) | lower is better |
| Real wage growth | Growth in average hourly earnings minus CPI inflation (pp). The CPI is the metro's own for 21 metros and its Census division's for the other 29. | higher is better |
| Openings | `jolts_state` (default): the job openings rate of the metro's principal state. `postings`: our own open analyst postings per 100k jobs. | higher is better |

**How it's built:**
1. Each component is z-scored across the 50 metros within each month. This puts different units on one scale.
2. The index is the weighted average of those z-scores. 0 means the average top-50 metro that month.
3. Weights are re-normalised when a metro lacks a component in a given month. `components_used` records which components went in.

**What's "accelerating":** a metro whose index rose over the last 3 months, meaning it is gaining relative to the other metros.

**Openings caveats:** official openings data does not exist below the state level.
- State JOLTS is now published once a year. The latest month in the data is December 2025, so it is dropped once it is more than 12 months old.
- Every metro in the same state gets the same value. For example, Dallas, Houston, Austin and San Antonio all share Texas's rate.
- The postings option is current, but it only covers the 40 companies we scrape.

## Nowcast

**Target:** next month's metro unemployment rate. This is the BLS LAUS rate, which is not seasonally adjusted.

**Baselines:**
- **Naive last value:** next month equals this month.
- **Seasonal naive:** next month equals the same month last year plus this month's year-over-year change.

**Model:** a ridge regression pooled across all 50 metros. It predicts the year-over-year change of next month's rate from five inputs:
- this month's year-over-year change in unemployment,
- last month's year-over-year change,
- job growth,
- the change in job growth over the last 3 months,
- the year-over-year change in the national unemployment rate.

The forecast is the same month last year plus the predicted change. The seasonal naive is a special case of this model, so the model only beats it by learning something real.

**Validation:**
- Expanding-window time-series cross-validation with 4 one-year folds, forecasting one month ahead. Each fold trains only on target months that come before it.
- March 2020 to December 2021 are left out of training, because pandemic swings distort a linear fit. They are still available as lags.
- Scores are MAPE and MAE in percentage points.

**Data gap:** BLS published no October 2025 metro unemployment rates because of the federal shutdown.
- October 2025 is never used as a forecast target.
- Where it is needed as a lag, it is interpolated from September and November 2025, and the row is flagged `uses_imputed_lag`.

## Cost of living

Pay is adjusted with **BEA Regional Price Parities** (all items, US = 100). The latest year BEA publishes is 2024, and it covers all 50 metros.

`median_wage_cost_adjusted` = OEWS median wage × 100 / RPP. That expresses the wage in national-average dollars.

If BEA ever stops publishing metro RPPs, the model falls back to the principal state's RPP. The column `rpp_geo_level` says which one was used.

## Interview talking points

- **Always compare with a naive baseline.** For metro unemployment, the seasonal naive is hard to beat, and saying so honestly is a stronger answer than claiming a big win.
- **Time-series cross-validation, not random K-fold.** Random folds leak the future into training.
- **Z-scoring within each month.** It makes components with different units comparable. It also makes the index relative, so a rising pulse means outperforming peers, not necessarily absolute growth.
- **Missing data is handled explicitly.** CPI is published every other month for most metros, JOLTS went annual, and October 2025 is missing because of the shutdown. Each gap is carried forward, dropped or interpolated, and every case is flagged.
