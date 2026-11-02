# Dashboard: Tableau Public build guide

**Click-by-click steps: [tableau_walkthrough.md](tableau_walkthrough.md).** This page is the design reference.

Built in **Tableau Public**. It's free, the desktop app runs natively on a Mac, and publishing gives you a public link that recruiters can open without an account.

Why not the alternatives:
- **Power BI Desktop** is Windows-only.
- **Power BI web, free tier:** sharing a report needs a Pro license, and "Publish to web" depends on tenant settings you don't control.

The 4 pages from the Power BI plan become 4 Tableau dashboards. DAX measures become calculated fields, and slicers become filters and parameters.

## 1. Data: the 8 report tables

`dashboard/report_tables.py` writes these files to `dashboard/data/report/`. The monthly GitHub Action rebuilds and commits them.

Every table already includes `metro`, `principal_state` and `census_region`, so each sheet uses one data source and no blends or joins are needed.

| Table | Grain | Used on page |
|---|---|---|
| `metro_ranking.csv` | 1 row per metro, latest month | 1 Ranking |
| `metro_monthly.csv` | metro × month, 2016 onward | 2 Deep dive |
| `metro_annual.csv` | metro × year | 2 Deep dive |
| `analyst_pay.csv` | metro × occupation (OEWS) | 3 Analyst pay & demand |
| `analyst_postings.csv` | posting × location | 3 Analyst pay & demand |
| `analyst_tools.csv` | posting × tool | 3 Analyst pay & demand |
| `nowcast_backtest.csv` | metro × month × method (out-of-sample) | 4 Nowcast |
| `nowcast_next.csv` | 1 row per metro, next month | 4 Nowcast |

### Connect (auto-refreshing)

1. **Google Sheet:** create one called **Metro Pulse data** with 8 tabs, each named like a table above. In A1 of each tab, put:
   ```
   =IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/metro_ranking.csv")
   ```
   Swap in each tab's file name. The monthly GitHub Action updates the CSVs, and the Sheet picks them up.
2. **Tableau Public:** install it from public.tableau.com (free; sign up for a profile). Open it, then **Connect → More… → Google Drive**, sign in, and pick **Metro Pulse data**.
3. **Data sources:** drag one tab onto the canvas. Then use **Data → New Data Source** to add each of the other tabs as its own data source, 8 in total, and rename each one after its tab. Keep them separate on purpose, because each one has a different grain.
4. **Field types** (click the type icon in the Data pane):
   - `cbsa_code` → String.
   - `month_date` and `target_month` → Date.
   - `year` → Number (whole), shown as a dimension.
5. **After publishing:** in Tableau Public, tick **Keep this data in sync with Google Sheets**. The public viz then refreshes daily from the Sheet, which refreshes from GitHub, and you never re-upload.

If the Google Sheets route gives you trouble, use **Connect → Text file** on the CSVs in `dashboard/data/report/` in your local clone. The viz then only updates when you re-publish it.

## 2. Parameters and calculated fields (the DAX equivalents)

**Parameter `Selected Metro`:**
- Data type String, Allowable values **List**.
- Click **Add values from → metro_ranking → metro**. Current value: Boston.
- Right-click it → **Show Parameter**.

A parameter isn't tied to one data source, which is why it can drive charts from several sources at once. That's the Tableau way to filter across sources.

| Data source | Calculated field | Formula | Power BI equivalent |
|---|---|---|---|
| metro_ranking | Momentum | `IF [pulse_change_3m] > 0 THEN "Accelerating" ELSE "Slowing" END` | calculated column |
| metro_ranking | Metros with rising unemployment | `SUM(IF [unemployment_change_yoy_pp] > 0 THEN 1 ELSE 0 END)` | `CALCULATE(COUNTROWS(...), ... > 0)` |
| metro_ranking | Median job growth | `MEDIAN([nonfarm_jobs_yoy_pct])` | `MEDIAN(...)` |
| metro_ranking | Is selected metro | `[metro] = [Selected Metro]` | `SELECTEDVALUE` logic |
| metro_monthly, metro_annual, nowcast_backtest | Is selected metro | `[metro] = [Selected Metro]` (create it in each source) | slicer |
| metro_monthly | Gap vs US unemployment (pp) | `[unemployment_rate] - [us_unemployment_rate]` | calculated column |
| analyst_pay | Cost-of-living effect ($) | `[annual_median_wage] - [median_wage_cost_adjusted]` | calculated column |
| analyst_postings | Postings | `COUNTD([job_key])` | `DISTINCTCOUNT(job_key)` |
| analyst_postings | Postings per 100k jobs | `COUNTD([job_key]) / MAX([metro_jobs_thousands]) * 100` | `DIVIDE([Postings], MAX(...)) * 100` |
| analyst_postings | Remote share | `COUNTD(IF [is_remote] THEN [job_key] END) / COUNTD([job_key])` | `DIVIDE(CALCULATE([Postings], is_remote), [Postings])` |
| analyst_tools | Postings mentioning tool | `COUNTD([job_key])` | `DISTINCTCOUNT(job_key)` |
| analyst_tools | Share of postings | `COUNTD([job_key]) / {FIXED : COUNTD([job_key])}` | `DIVIDE([Postings], CALCULATE([Postings], ALL(tool)))` |
| nowcast_backtest | MAPE % | `AVG([abs_pct_error])` | `AVERAGE(abs_pct_error)` |
| nowcast_backtest | MAE (pp) | `AVG([abs_error_pp])` | `AVERAGE(abs_error_pp)` |

If `is_remote` comes in as text, use `[is_remote] = "true"` in Remote share.

The `{FIXED : ...}` expression is a **level of detail (LOD) expression**. It's Tableau's version of DAX's `ALL()`: it computes the total over all tools, ignoring the tool on each row.

## 3. Worksheets and dashboards

Build each chart as its own **worksheet**, then arrange the worksheets on a **dashboard** (1200 × 800, fixed size). Use one color palette across the workbook: blue for values, and a red-blue diverging palette only where the sign matters (pulse, changes).

### Dashboard 1: Metro ranking
Question it answers: *which metros are strongest right now, and who is moving?*

- **Filters (show as drop-downs, apply to all worksheets using this data source):** `census_region`, `cpi_geo_level`, `Momentum`.
- **Worksheets:**
  - **KPI tiles.** One text sheet each for `Median job growth`, `Metros with rising unemployment`, and MAX(`month_date`) labeled "Data through".
  - **Pulse bar chart.**
    - Rows `metro`, Columns `SUM(pulse)`, sorted descending.
    - Color `pulse`, diverging palette centered at 0.
    - Add a reference line at 0.
  - **Ranking table.**
    - Rows `metro`. Measure Names/Values: `pulse_rank`, `rank_change_3m`, `nonfarm_jobs_yoy_pct`, `unemployment_rate`, `unemployment_change_yoy_pp`, `real_wage_growth_pp`, `openings`.
    - Sort by `pulse_rank`.
  - **Scatter.** Columns `nonfarm_jobs_yoy_pct`, Rows `unemployment_change_yoy_pp`, Detail `metro`, Size `population`, Label on hover. Top-left = jobs up and unemployment down.
- **Dashboard action:** clicking a metro in the bar chart sets **Selected Metro** (Dashboard → Actions → Change Parameter). This is the jump into Dashboard 2.
- **Footnote:** "Pulse = weighted z-scores vs the other 49 metros (0 = average). Openings = state JOLTS, last published Dec 2025."

### Dashboard 2: Metro deep dive
Question: *how is one metro doing over time, and what is it like?*

- **Controls:** the `Selected Metro` parameter, plus a `month_date` range filter (relative: last 5 years).
- On every worksheet here, put **Is selected metro = True** on Filters.
- **Worksheets:**
  - **KPI tiles** (metro_ranking): `pulse`, `pulse_rank`, `unemployment_rate`, `nonfarm_jobs_yoy_pct`, `real_wage_growth_pp`.
  - **Unemployment vs US** (metro_monthly). Columns MONTH(`month_date`), Rows `unemployment_rate` and `us_unemployment_rate` on a dual axis (synchronize axes).
  - **Job growth** line: `nonfarm_jobs_yoy_pct`.
  - **Pulse** line: `pulse`.
  - **Real wage growth** bars: `real_wage_growth_pct`. Most metros only have it every other month because their CPI is bimonthly.
  - **Annual context table** (metro_annual). Rows `year` (descending). Columns `per_capita_income_usd`, `median_household_income`, `pct_bachelors_or_higher`, `poverty_rate`, `rent_burdened_pct`, `fhfa_hpi_yoy_pct`.
- **Title:** insert the parameter into the dashboard title: "Deep dive: <Selected Metro>".

### Dashboard 3: Analyst pay and demand
Question: *where does analyst pay go furthest, and who is hiring for what?*

- **Filters:** `occupation_title` (single value drop-down, default Data Scientists), `census_region`, `role_family`.
- **Worksheets:**
  - **Pay bars** (analyst_pay).
    - Rows `metro`, Columns `median_wage_cost_adjusted`, with `annual_median_wage` as a reference marker. You can do that with a bar-in-bar chart: dual axis, synchronized.
    - Top 15 via a Top N filter on `metro`.
  - **Pay vs prices scatter.** Columns `rpp`, Rows `annual_median_wage`, Detail `metro`. Top-left = high pay, low prices.
  - **Pay table.** `metro`, `annual_median_wage`, `rpp`, `median_wage_cost_adjusted`, `pay_vs_all_occupations`, `employment`.
  - **Postings by location** (analyst_postings). Rows `location_label`, Columns `Postings`, top 15.
  - **Postings per 100k jobs.** Same chart with the `Postings per 100k jobs` measure, filtered to `location_class = metro`.
  - **Tools** (analyst_tools). Rows `tool`, Columns `Share of postings`, top 12, formatted as %.
  - **KPI tiles:** `Postings`, `Remote share`.
- **Footnote:** "Pay: OEWS May 2025, adjusted by BEA Regional Price Parities 2024. Postings: public Greenhouse/Lever boards of 40 companies, a snapshot, not the whole market."

### Dashboard 4: Nowcast vs actual
Question: *how good is the nowcast, and what does it say for next month?*

- **Controls:** `Selected Metro` parameter, plus a `method` filter (multiple values).
- **Worksheets:**
  - **Forecast vs actual** (nowcast_backtest, filter Is selected metro = True).
    - Columns MONTH(`target_month`), Rows AVG(`forecast`), Color `method`.
    - Put AVG(`actual`) on a dual axis as a thick black line, synchronized.
  - **MAPE by fold.** Rows `fold`, Columns `method`, Text and Color `MAPE %` (highlight table).
  - **MAPE tiles.** `MAPE %` with `method` on Columns, all metros.
  - **Next-month watchlist** (nowcast_next). Rows `metro`, Columns `nowcast_yoy_pp`, top 10, sorted descending.
  - **Nowcast table.** `metro`, `latest_rate`, `nowcast`, `pred_seasonal_naive`, `uses_imputed_lag`.
- **Footnote:** "One-month-ahead, expanding-window CV, 4 yearly folds. Oct 2025 was never published (shutdown); where it's needed as a lag it is interpolated."

## 4. Publish and share (free)

1. **File → Save to Tableau Public As…**, named "US Metro Economic Pulse". It opens in your browser.
2. On the viz page, open **Settings**:
   - Tick **Keep this data in sync**.
   - Turn on **Show Viz on Profile**.
   - Optionally allow downloads, so people can see your calculated fields.
3. Click **Download → PDF** (all dashboards) and save it as `dashboard/metro_pulse_report.pdf`.
4. Take a screenshot of each dashboard: `dashboard/screenshots/1_ranking.png` … `4_nowcast.png`.
5. Commit the PDF and screenshots, and put the Tableau Public link at the top of the README.

## 5. Interview talking points

- **Flat tables per dashboard.** Joins happen once upstream (dbt + `report_tables.py`), so the BI layer stays simple and every data source has one clear grain.
- **A parameter instead of a filter for cross-source selection.** One `Selected Metro` drives all 4 data sources. Clicking a metro on the ranking changes it, which gives you drill-through without blending.
- **LOD expressions are DAX's `CALCULATE`/`ALL`.** "Share of postings" divides by `{FIXED : COUNTD(job_key)}` so the ratio stays correct at any level of detail.
- **Honesty in the visuals.** The footnotes carry the data caveats: state-level openings, the bimonthly CPI, the shutdown gap, and the postings sample.
