# Tableau Public walkthrough: click by click

Follow the phases in order. Each phase ends with a **Checkpoint** describing what you should see. If you don't see it, send a screenshot. Total time is about 2–3 hours, and you can stop after any phase: Tableau saves your workbook to your Tableau Public profile (Phase 8). Until then, keep the app open or use **File → Save to Tableau Public** as a draft.

Field names below are written `like_this`. In Tableau they appear exactly like that in the left-hand **Data** pane.

---

## Phase 0: Install (10 min)

1. Go to **public.tableau.com**, then **Sign Up**. Make a free profile and confirm the email.
2. On the same site, click **Create → Download Tableau Public** and install the Mac app.
3. Open Tableau Public and sign in with your new profile when it asks.

**Checkpoint:** the Tableau Public start page, with a **Connect** list on the left.

---

## Phase 1: Google Sheet that pulls the data from GitHub (10 min)

1. Go to **sheets.new** to create a blank Google Sheet. Rename it **Metro Pulse data** (click "Untitled spreadsheet" at the top left).
2. Create 8 tabs. Click **+** at the bottom left 7 times, then double-click each tab to rename it. Use these exact names:
   `metro_ranking`, `metro_monthly`, `metro_annual`, `analyst_pay`, `analyst_postings`, `analyst_tools`, `nowcast_backtest`, `nowcast_next`
3. In each tab, click cell **A1** and paste the matching formula:

| Tab | Paste into A1 |
|---|---|
| metro_ranking | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/metro_ranking.csv")` |
| metro_monthly | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/metro_monthly.csv")` |
| metro_annual | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/metro_annual.csv")` |
| analyst_pay | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/analyst_pay.csv")` |
| analyst_postings | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/analyst_postings.csv")` |
| analyst_tools | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/analyst_tools.csv")` |
| nowcast_backtest | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/nowcast_backtest.csv")` |
| nowcast_next | `=IMPORTDATA("https://raw.githubusercontent.com/khus-hi/us-metro-economic-pulse/main/dashboard/data/report/nowcast_next.csv")` |

4. Wait a few seconds for each tab to fill.

**Checkpoint:**
- `metro_ranking` has 51 rows: a header plus 50 metros.
- `metro_monthly` has about 6,450 rows.
- If a cell shows **#ERROR!** with "result too large", open that CSV link in your browser, save the file, delete the formula, and use **File → Import → Upload → Replace current sheet**.

---

## Phase 2: Connect Tableau to the Sheet (15 min)

1. On the start page, under **Connect → To a Server**, click **More… → Google Drive** (Tableau Public's Google Sheets connector). A browser window opens. Sign in with the same Google account and click **Allow**.
2. Pick **Metro Pulse data** and click **Connect**.
3. You're now on the **Data Source** page. On the left, under *Sheets*, drag **metro_ranking** onto the big empty canvas.
4. Rename this source: at the top, click the name (e.g. "Metro Pulse data") and type **metro_ranking**.
5. Add the other 7 tabs as **separate** data sources. Repeat for each:
   1. Menu **Data → New Data Source → Google Drive**, pick **Metro Pulse data**, and click Connect.
   2. Drag that tab onto the canvas and rename the source to the tab name.

   Don't drag two tabs onto one canvas. Each table has a different grain, so each must be its own source.
6. Fix field types. On each source's Data Source page, the grid shows a small icon above every column (Abc, #, calendar). Click the icon to change the type:
   - `cbsa_code` → **String**, in every source that has it.
   - `month_date` (metro_ranking, metro_monthly) and `target_month` (nowcast_backtest, nowcast_next) → **Date**.
   - `year` (metro_annual) → **Number (whole)**.
   - If a percentage column shows **Abc**, set it to **Number (decimal)**.
7. Click **Sheet 1** at the bottom to open the first worksheet.

**Checkpoint:** the Data pane at top left lists all 8 data sources. Clicking each one shows its fields.

---

## Phase 3: The metro parameter and calculated fields (20 min)

### 3a. Parameter
1. In the Data pane, click the small **▼** next to the search box, then **Create Parameter…**
2. Fill in:
   - Name: **Selected Metro**
   - Data type: **String**
   - Allowable values: **List**
3. Click **Add values from → metro_ranking → metro**. All 50 names appear.
4. Set Current value to **Boston** and click OK.
5. Under *Parameters* at the bottom of the Data pane, right-click **Selected Metro → Show Parameter**.

### 3b. Calculated fields
For each row below:
1. In the Data pane, click the data source named in the first column so it's selected.
2. Use **Analysis → Create Calculated Field…**
3. Type the name, paste the formula, and click **OK**. You should see "The calculation is valid" at the bottom before clicking OK.

| Data source | Name | Formula |
|---|---|---|
| metro_ranking | Momentum | `IF [pulse_change_3m] > 0 THEN "Accelerating" ELSE "Slowing" END` |
| metro_ranking | Metros with rising unemployment | `SUM(IF [unemployment_change_yoy_pp] > 0 THEN 1 ELSE 0 END)` |
| metro_ranking | Median job growth | `MEDIAN([nonfarm_jobs_yoy_pct])` |
| metro_ranking | Is selected metro | `[metro] = [Selected Metro]` |
| metro_monthly | Is selected metro | `[metro] = [Selected Metro]` |
| metro_annual | Is selected metro | `[metro] = [Selected Metro]` |
| nowcast_backtest | Is selected metro | `[metro] = [Selected Metro]` |
| analyst_postings | Postings | `COUNTD([job_key])` |
| analyst_postings | Postings per 100k jobs | `COUNTD([job_key]) / MAX([metro_jobs_thousands]) * 100` |
| analyst_postings | Remote share | `COUNTD(IF [is_remote] THEN [job_key] END) / COUNTD([job_key])` |
| analyst_tools | Share of postings | `COUNTD([job_key]) / MIN({FIXED : COUNTD([job_key])})` |
| nowcast_backtest | MAPE % | `AVG([abs_pct_error])` |

If **Remote share** says the calculation has an error, `is_remote` came in as text. Use `[is_remote] = "true"` (or `"TRUE"`) in place of `[is_remote]`.

To format a share as a percentage, right-click **Remote share** or **Share of postings** in the Data pane, then **Default Properties → Number Format → Percentage**, 0 decimals.

**Checkpoint:** each new field appears with an **=** icon in its data source, and *Selected Metro* shows as a drop-down at the right side of the worksheet.

---

## How to build any worksheet (read once)

- **New worksheet:** click the first icon at the bottom of the window, to the right of the tabs. Double-click the tab to rename it.
- **Drag** fields from the Data pane onto **Columns** or **Rows** (shelves above the chart) or onto the **Marks** card (Color, Size, Label, Detail, Tooltip, Text).
- Only use fields from **one data source per worksheet**. Click the source in the Data pane first.
- **Sort:** hover over an axis and click the sort icon that appears, or click a pill's ▼ → Sort.
- **Filter:** drag a field onto the **Filters** shelf, choose values, and click OK. Then click the pill's ▼ → **Show Filter** to get an on-screen control.
- A measure pill reads like **SUM(pulse)**. Each table here has one row per metro (or metro-month), so SUM equals the value itself.

---

## Phase 4: Dashboard 1, Metro ranking (40 min)

**Sheet "Pulse bars"** (source: metro_ranking)
1. Drag **metro** → Rows. Drag **pulse** → Columns.
2. Sort descending (sort icon on the pulse axis).
3. Drag **pulse** onto **Color**. Click Color → **Edit Colors**:
   - Palette **Red-Blue Diverging**.
   - Click **Advanced >>** and tick **Center: 0**. Click OK.
4. Right-click the pulse axis → **Add Reference Line** → Value **Constant 0** → OK.

**Sheet "Ranking table"** (metro_ranking)
1. Drag **metro** → Rows.
2. Double-click, in this order: **pulse_rank, rank_change_3m, pulse, nonfarm_jobs_yoy_pct, unemployment_rate, unemployment_change_yoy_pp, real_wage_growth_pp, openings**. Tableau builds a text table using *Measure Names* and *Measure Values*.
3. Click the **metro** pill ▼ → **Sort** → Sort By **Field** → **pulse_rank**, **Ascending**, Aggregation Sum.
4. Optional: right-click each column header → **Edit Alias** for nicer names, e.g. "Job growth %".

**Sheet "Jobs vs unemployment"** (metro_ranking)
1. Drag **nonfarm_jobs_yoy_pct** → Columns and **unemployment_change_yoy_pp** → Rows.
2. Drag **metro** → **Detail**, **population** → **Size**, and **Momentum** → **Color**.
3. Right-click each axis → **Add Reference Line** → Constant 0.

**KPI sheets**, one per number (metro_ranking)
1. New sheet "KPI job growth": drag **Median job growth** onto **Text**. Click **Text → …** and type `Median job growth` on line 1, with the field on line 2. Make the field 28 pt.
2. Repeat as "KPI rising unemployment" with **Metros with rising unemployment**.
3. Repeat as "KPI data month" with **month_date**: right-click the pill → **Attribute**, then format it as Month Year.

**Assemble the dashboard**
1. Click the second icon at the bottom (**New Dashboard**) and rename it **1 Metro ranking**.
2. Left panel, **Size: Fixed size, 1200 × 800**.
3. Drag the sheets onto the canvas:
   - the 3 KPI sheets across the top,
   - Pulse bars on the left,
   - Ranking table on the right,
   - the scatter at the bottom right.
4. Filters:
   1. On the Pulse bars sheet, drag **census_region** → Filters → **All** → OK.
   2. ▼ → Show Filter.
   3. Back on the dashboard, click the filter card's ▼ → **Apply to Worksheets → All Using This Data Source**.
   4. Do the same for **cpi_geo_level** and **Momentum**.
5. Click **Dashboard → Show Title**. Double-click the title and type `US Metro Economic Pulse: metro ranking`.
6. From the left panel *Objects*, drag a **Text** box to the bottom and type:
   > Pulse = weighted z-scores of job growth, unemployment change, real wage growth and openings vs the other 49 metros (0 = average). Openings = state JOLTS, last published Dec 2025. Sources: BLS, BEA, Census.

Do the click-through actions after Dashboard 2 exists (Phase 5, step 8).

**Checkpoint:** 50 sorted bars, with Salt Lake City at the top, which matches the memo.

---

## Phase 5: Dashboard 2, Metro deep dive (40 min)

On **every** sheet in this phase, drag **Is selected metro** → Filters → tick **True** → OK.

**Sheet "Unemployment vs US"** (metro_monthly)
1. Drag **month_date** → Columns. Right-click the pill and pick the **second "Month"** in the list (the one showing "May 2015"), which makes it continuous and green.
2. Drag **unemployment_rate** → Rows.
3. Drag **us_unemployment_rate** onto the **left axis** of the chart and drop it when you see a double-ruler icon. You now have two lines.
4. Drag **month_date** → Filters → **Relative dates → Years → Last 5 years** → OK.

**Sheets "Job growth", "Pulse trend", "Real wage growth"** (metro_monthly)
1. Same date setup as above (steps 1 and 4).
2. Rows: **nonfarm_jobs_yoy_pct** / **pulse** / **real_wage_growth_pct** respectively.
3. For Real wage growth, change the Marks type (drop-down on the Marks card) to **Bar**.

**Sheet "KPI metro"** (metro_ranking)
- Drag **pulse_rank, pulse, unemployment_rate, nonfarm_jobs_yoy_pct, real_wage_growth_pp** onto **Text**, then edit the text into one line each.

**Sheet "Annual context"** (metro_annual)
1. Right-click **year** in the Data pane → **Convert to Dimension**, then **Convert to Discrete**. Drag it → Rows, then ▼ → Sort descending.
2. Double-click **per_capita_income_usd, median_household_income, pct_bachelors_or_higher, poverty_rate, rent_burdened_pct, fhfa_hpi_yoy_pct**.

**Assemble**
1. New Dashboard **2 Metro deep dive**, fixed size 1200 × 800.
2. Layout: KPI across the top, the 4 trend charts in a 2 × 2 grid, Annual context at the bottom.
3. Show the **Selected Metro** parameter: click a sheet, then ▼ → **Parameters → Selected Metro**.
4. Title: **Dashboard → Show Title**. Double-click it, type `Deep dive: `, then **Insert → Parameters.Selected Metro**.
5. Test it: change the parameter to Seattle and every chart should change.
6. Go back to **1 Metro ranking** and add the click-through actions.
7. First action: **Dashboard → Actions → Add Action → Change Parameter**:
   - Source sheet **Pulse bars**, Run action on **Select**.
   - Target parameter **Selected Metro**, Field **metro**.
   - Click OK.
8. Second action: **Add Action → Go to Sheet**:
   - Source **Pulse bars**, Run on **Select**.
   - Target sheet **2 Metro deep dive**.
   - Click OK twice.

**Checkpoint:** clicking Denver's bar on dashboard 1 opens the deep dive titled "Deep dive: Denver".

---

## Phase 6: Dashboard 3, Analyst pay and demand (40 min)

**Sheet "Pay after cost of living"** (analyst_pay)
1. Drag **occupation_title** → Filters → select **Data Scientists** only → OK → ▼ Show Filter. On the filter card ▼, choose **Single Value (dropdown)**.
2. Drag **metro** → Rows and **median_wage_cost_adjusted** → Columns. Sort descending.
3. Drag **metro** → Filters → **Top** tab → **By field: Top 15 by median_wage_cost_adjusted (Sum)** → OK.
4. Drag **annual_median_wage** and **rpp** onto **Tooltip**, and **median_wage_cost_adjusted** onto **Label**.
5. Right-click the occupation_title pill on Filters → **Add to Context**. This makes Top 15 respect the occupation filter.

**Sheet "Pay vs prices"** (analyst_pay)
- Same occupation filter.
- Columns **rpp**, Rows **annual_median_wage**, **metro** → Detail and also → Label.

**Sheet "Pay table"** (analyst_pay)
- Same occupation filter.
- Rows **metro**. Double-click **annual_median_wage, rpp, median_wage_cost_adjusted, pay_vs_all_occupations, employment**.

**Sheet "Postings by location"** (analyst_postings)
- Rows **location_label**, Columns **Postings**. Sort descending, Top 15 by Postings (same as step 3 above).

**Sheet "Postings per 100k jobs"** (analyst_postings)
- Filter **location_class** = metro.
- Rows **metro**, Columns **Postings per 100k jobs**. Sort descending.

**Sheet "Top tools"** (analyst_tools)
- Rows **tool**, Columns **Share of postings**. Sort descending, Top 12 by Share of postings.

**Sheet "KPI postings"** (analyst_postings)
- **Postings** and **Remote share** on Text.

**Assemble**
1. Create **3 Analyst pay and demand** with pay charts on the left, postings and tools on the right, KPIs on top.
2. Make the occupation filter apply to all 3 pay sheets: on the filter card ▼ → **Apply to Worksheets → Selected Worksheets** → tick the 3 pay sheets.
3. On a postings sheet, drag **role_family** to Filters → Show Filter. On the dashboard, apply it to all sheets using this data source.
4. Add a footnote text box:
   > Pay: OEWS May 2025 medians, divided by BEA Regional Price Parities 2024 (US = 100). Postings: public Greenhouse/Lever boards of 40 companies, a snapshot, not the whole market.

**Checkpoint:** with Data Scientists selected, the top 3 bars are San Jose, Seattle and San Francisco.

---

## Phase 7: Dashboard 4, Nowcast vs actual (30 min)

**Sheet "Forecast vs actual"** (nowcast_backtest)
1. Filters: **Is selected metro** = True.
2. Columns: **target_month** as continuous Month (same trick as Phase 5).
3. Rows: **forecast**. Then right-click the pill → Measure → **Average**.
4. Drag **method** → Color.
5. Drag **actual** → Rows, next to forecast, and set it to Average too. Right-click the actual pill → **Dual Axis**, then right-click the right axis → **Synchronize Axis**.
6. On the Marks card, open the **AVG(actual)** tab. Drag **method** off it, then set Color to black and Size a little thicker.

**Sheet "MAPE by fold"** (nowcast_backtest)
- Rows **fold**, Columns **method**.
- **MAPE %** → Color and → Text.
- Marks type **Square**.

**Sheet "MAPE overall"** (nowcast_backtest)
- Columns **method**, **MAPE %** → Text. Format the text to 2 decimals.

**Sheet "Next month watchlist"** (nowcast_next)
- Rows **metro**, Columns **nowcast_yoy_pp**. Sort descending, Top 10.

**Sheet "Nowcast table"** (nowcast_next)
- Rows **metro**. Double-click **latest_rate, nowcast, pred_seasonal_naive**. Drag **uses_imputed_lag** → Rows.

**Assemble**
1. Create **4 Nowcast vs actual** and show the Selected Metro parameter.
2. Add a footnote:
   > One-month-ahead forecasts, expanding-window time-series CV, 4 yearly folds. BLS published no Oct 2025 metro data (shutdown); where needed as a lag it is interpolated.

**Checkpoint:** MAPE overall shows Ridge model 4.87, Seasonal naive 4.92 and Last value 7.20, which matches findings.md.

---

## Phase 8: Publish, keep it fresh, and add it to the repo (20 min)

1. **File → Save to Tableau Public As…** and name it **US Metro Economic Pulse**.
   - If the save dialog offers **Keep this data in sync with Google Sheets**, tick it.
   - Your browser opens the published viz.
2. If you didn't see the sync option, look for it on the viz page under **Settings** (the gear or "…" menu). It refreshes your public viz from the Sheet daily, and the Sheet refreshes from GitHub.
3. Also under Settings, turn on **Show Viz on Profile**. Allowing workbook download is optional and lets people see your formulas.
4. **PDF:** on the viz page, click the **Download** icon (bottom toolbar) → **PDF** → *Specific sheets from this workbook* → select the 4 dashboards → Download.
5. **Screenshots:** for each dashboard, use **Download → Image**, or press Cmd+Shift+4, then Space, then click the browser window.
6. Put the files in your repo and push:
   ```
   mkdir -p dashboard/screenshots
   mv ~/Downloads/<pdf name>.pdf dashboard/metro_pulse_report.pdf
   mv ~/Downloads/<image 1>.png dashboard/screenshots/1_ranking.png
   mv ~/Downloads/<image 2>.png dashboard/screenshots/2_deep_dive.png
   mv ~/Downloads/<image 3>.png dashboard/screenshots/3_analyst_pay_demand.png
   mv ~/Downloads/<image 4>.png dashboard/screenshots/4_nowcast.png
   git add dashboard/metro_pulse_report.pdf dashboard/screenshots
   git commit -m "dashboard: Tableau Public PDF export and screenshots"
   git push
   ```
7. Copy the viz URL from the browser for your README.

**Checkpoint:** an incognito window can open your viz link without logging in.
