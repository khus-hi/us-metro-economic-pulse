# Dashboard: Looker Studio build guide

You're on a Mac and Power BI Desktop only runs on Windows, so this report is built in **Looker Studio**. It's free with a Google account and needs no credit card.

The 4 pages are the same ones planned for Power BI. DAX measures become Looker Studio *calculated fields*, and slicers become *controls*.

## 1. Data: the 8 report tables

`dashboard/report_tables.py` writes these files to `dashboard/data/report/`. The monthly GitHub Action rebuilds and commits them.

Every table already includes `metro`, `principal_state` and `census_region`, so you never need a data blend.

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

### Connect them through a Google Sheet so the report refreshes itself

1. Create a Google Sheet called **Metro Pulse data** with 8 tabs, each named exactly like a table above (without `.csv`).
2. In cell A1 of each tab, enter a formula like this one, swapping in the tab's file name:
   ```
   =IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/metro_ranking.csv")
   ```
   Each month the Action commits new CSVs, and the Sheet picks them up the next time it recalculates. You don't upload anything by hand.
3. If a tab shows `#ERROR` or "Result too large", use **File → Import → Upload** for that CSV instead. That tab then needs a manual re-import each month.

### Add the data sources in Looker Studio

1. Go to lookerstudio.google.com and choose **Blank report**.
2. Add data with **Google Sheets → Metro Pulse data**. Pick a tab and keep "Use first row as headers" checked. Repeat for all 8 tabs.
3. In each data source (**Resource → Manage added data sources → Edit**), set these field types:
   - `cbsa_code`: **Text**. Otherwise leading zeros get dropped.
   - `month_date` and `target_month`: **Date (YYYY-MM-DD)**. `rpp_year` and `year`: **Year**.
   - Rates and percentages: **Number**. They are already in percent units (4.5 means 4.5%), so do **not** pick the Percent type.

## 2. Calculated fields (the DAX equivalents)

Add each one in the data source named in the first column (**Edit → Add a field**).

| Data source | Field name | Formula | Power BI equivalent |
|---|---|---|---|
| metro_ranking | Momentum | `CASE WHEN pulse_change_3m > 0 THEN "Accelerating" ELSE "Slowing" END` | calculated column |
| metro_ranking | Metros with rising unemployment | `SUM(CASE WHEN unemployment_change_yoy_pp > 0 THEN 1 ELSE 0 END)` | `CALCULATE(COUNTROWS(...), unemployment_change_yoy_pp > 0)` |
| metro_ranking | Median job growth | `MEDIAN(nonfarm_jobs_yoy_pct)` | `MEDIAN(...)` |
| metro_monthly | Gap vs US unemployment (pp) | `unemployment_rate - us_unemployment_rate` | calculated column |
| analyst_pay | Cost-of-living effect ($) | `annual_median_wage - median_wage_cost_adjusted` | calculated column |
| analyst_postings | Postings | `COUNT_DISTINCT(job_key)` | `DISTINCTCOUNT(job_key)` |
| analyst_postings | Postings per 100k jobs | `COUNT_DISTINCT(job_key) / MAX(metro_jobs_thousands) * 100` | `DIVIDE([Postings], MAX(...)) * 100` |
| analyst_postings | Remote share | `COUNT_DISTINCT(CASE WHEN is_remote THEN job_key ELSE NULL END) / COUNT_DISTINCT(job_key)` | `DIVIDE(CALCULATE([Postings], is_remote), [Postings])` |
| analyst_tools | Postings mentioning tool | `COUNT_DISTINCT(job_key)` | `DISTINCTCOUNT(job_key)` |
| nowcast_backtest | MAPE % | `AVG(abs_pct_error)` | `AVERAGE(abs_pct_error)` |
| nowcast_backtest | MAE (pp) | `AVG(abs_error_pp)` | `AVERAGE(abs_error_pp)` |

If `is_remote` arrives as text rather than a boolean, use `is_remote = "true"` in the Remote share formula.

## 3. Pages

Use one theme for all pages (**Theme and layout → Simple**) with a single accent color. Put the same header on every page: the title, the data month, and a "Source: BLS, BEA, Census, OEWS" text box.

### Page 1: Metro ranking
Question it answers: *which metros are strongest right now, and who is moving?*

- **Controls (top row):** Drop-down list on `census_region`, drop-down on `cpi_geo_level`, drop-down on `Momentum`.
- **Scorecards:**
  - `Median job growth`.
  - `Metros with rising unemployment`.
  - `month_date` (aggregation MAX), labeled "Data through".
- **Bar chart:** dimension `metro`, metric `pulse` (Sum), sorted descending, 50 bars. Style it with a single color, plus a reference line at 0.
- **Table with heat map:** dimension `metro`. Metrics:
  - `pulse_rank`
  - `rank_change_3m`
  - `pulse`
  - `nonfarm_jobs_yoy_pct`
  - `unemployment_rate`
  - `unemployment_change_yoy_pp`
  - `real_wage_growth_pp`
  - `openings`

  Turn on **Style → Heatmap** for the z-type columns. Sort by `pulse_rank` ascending.
- **Scatter chart:**
  - dimension `metro`, X `nonfarm_jobs_yoy_pct`, Y `unemployment_change_yoy_pp`, bubble size `population`.
  - The top-left quadrant means jobs are growing and unemployment is falling.
- **Footnote text box:** "Pulse = weighted z-scores vs the other 49 metros (0 = average). Openings = state JOLTS, last published Dec 2025."

### Page 2: Metro deep dive
Question: *how is one metro doing over time, and what is it like?*

- **Controls:**
  - **Drop-down on `metro`**, single select, default Boston. It filters every chart on the page, because all the tables share the `metro` field name. If one chart doesn't follow it, open that chart and confirm it uses a data source that has the `metro` field.
  - Date range control, default "Last 5 years".
- **Scorecards (metro_ranking):** `pulse`, `pulse_rank`, `unemployment_rate`, `nonfarm_jobs_yoy_pct`, `real_wage_growth_pp`.
- **Time series charts (metro_monthly), with `month_date` as the dimension:**
  - `unemployment_rate` and `us_unemployment_rate` (two lines).
  - `nonfarm_jobs_yoy_pct`.
  - `pulse`.
  - `real_wage_growth_pct`. Set "Missing data → Linear interpolation" because CPI is bimonthly for most metros.
- **Table (metro_annual):** dimension `year`. Metrics:
  - `per_capita_income_usd`
  - `median_household_income`
  - `pct_bachelors_or_higher`
  - `poverty_rate`
  - `rent_burdened_pct`
  - `fhfa_hpi_yoy_pct`

  Sort by year descending.

### Page 3: Analyst pay and demand
Question: *where does analyst pay go furthest, and who is hiring for what?*

- **Controls:** drop-down on `occupation_title` (default Data Scientists), drop-down on `census_region`, drop-down on `role_family` (postings).
- **Bar chart (analyst_pay):**
  - dimension `metro`, metrics `median_wage_cost_adjusted` and `annual_median_wage`, top 15, sorted by the adjusted value.
  - Title: "Median pay, nominal vs after cost of living (BEA RPP 2024)".
- **Scatter (analyst_pay):** X `rpp`, Y `annual_median_wage`, dimension `metro`. Metros high on Y and low on X are the "pay goes furthest" corner.
- **Table (analyst_pay):** `metro`, `annual_median_wage`, `rpp`, `median_wage_cost_adjusted`, `pay_vs_all_occupations`, `employment`.
- **Bar chart (analyst_postings):** dimension `location_label`, metric `Postings`, top 15. Add a second chart with `Postings per 100k jobs`, filtered to `location_class = metro`.
- **Bar chart (analyst_tools):** dimension `tool`, metric `Postings mentioning tool`, top 12.
- **Scorecards:** `Postings` and `Remote share`.
- **Footnote:** "Postings = public Greenhouse/Lever boards of 40 companies; a snapshot, not the whole market."

### Page 4: Nowcast vs actual
Question: *how good is the nowcast, and what does it say for next month?*

- **Controls:** drop-down on `metro` (single select) and drop-down on `method`.
- **Time series (nowcast_backtest):**
  - dimension `target_month`, breakdown dimension `method`, metric `forecast`.
  - Add a second time series chart for `actual` and lay it over the first, or use a combo chart with `actual` as a line.
- **Pivot table (nowcast_backtest):** rows `fold`, columns `method`, metric `MAPE %`, with a heat map.
- **Scorecards:** `MAPE %` filtered to each method, three in total, using chart-level filters `method = Ridge model`, `Seasonal naive` and `Last value`.
- **Bar chart (nowcast_next):** dimension `metro`, metric `nowcast_yoy_pp`, top 10.
- **Table (nowcast_next):** `metro`, `latest_rate`, `nowcast`, `pred_seasonal_naive`, `uses_imputed_lag`.
- **Footnote:** "One-month-ahead, expanding-window CV, 4 yearly folds. Oct 2025 was never published (shutdown); where needed as a lag it is interpolated."

## 4. Share it (free)

1. **Share → Manage access → Anyone with the link can view.** Put that link at the top of the README.
2. **File → Download → PDF**, all pages. Save it as `dashboard/metro_pulse_report.pdf`.
3. Take a screenshot of each page and save them as `dashboard/screenshots/1_ranking.png` through `4_nowcast.png`. Commit the PDF and the screenshots so recruiters can see the report without opening Looker Studio.

## 5. Interview talking points

- **Flat tables per page.** Joins happen once, in Python (dbt + `report_tables.py`), so the BI layer stays simple and fast.
- **A metric layer in calculated fields, the same idea as DAX measures.** Ratios such as Remote share are computed at the right grain with COUNT_DISTINCT, never as an average of per-row ratios.
- **Honesty in the visuals.** The footnotes carry the data caveats: state-level openings, the bimonthly CPI, the shutdown gap, and the postings sample.
