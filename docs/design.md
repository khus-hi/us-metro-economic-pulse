# US Metro Economic Pulse: Design Proposal

Status: proposal, no code yet. Written 2026-11-01.
Every ID below was checked against an official page on that date unless it is marked **[verify]**. Anything marked **[verify]** gets confirmed by the first ingest script (it will fail loudly if an ID returns nothing) before any number is shown.

> **Interview soundbite:** "Before writing code I verified each source's geography and release schedule. That's how I caught that BEA stopped publishing metro GDP in 2026 and that JOLTS has no official metro data, and designed around both."

---

## 1. Headline findings (read this first)

| Source | Metro-level? | What I propose |
|---|---|---|
| BLS LAUS (unemployment) | Yes, monthly, every MSA | Use directly |
| BLS CES State & Metro (jobs, earnings) | Yes, monthly | Use directly |
| **BLS JOLTS** | **No.** Official data is national + state only. The MSA series was a one-time research release for 18 MSAs that ended Dec 2019 ([BLS](https://www.bls.gov/jlt/jlt_msadata.htm)). | Show the metro's **state** JOLTS rates as context, and use our own job-postings counts as the metro "demand" signal |
| **BEA metro GDP & personal income** | **No longer.** BEA discontinued all MSA/micro/CSA statistics starting with the 2024 estimates ([release, Feb 5 2026](https://www.bea.gov/news/2026/gross-domestic-product-county-and-personal-income-county-2024); [FAQ 1481](https://bea.gov/help/faq/1481)). | Pull **county** tables and sum counties to CBSAs ourselves with the crosswalk. Nominal GDP and income add up cleanly; real GDP does not (see §2.4) |
| **BLS CPI (prices)** | **Only 23 areas**, of which ~21 are top-50 metros. 3 are monthly (NY, LA, Chicago), the rest bimonthly ([BLS](https://www.bls.gov/cpi/additional-resources/geographic-revision-2018.htm)) | Metro CPI where it exists; otherwise the **Census-division CPI** for the metro's division, flagged in the dashboard as "regional proxy" |
| Census ACS 2024 5-year | Yes, every CBSA | Use directly (released Jan 29, 2026, uses July 2023 OMB delineations) |
| BLS OEWS May 2025 | Yes, MSA file | Use directly (uses 2023 delineations since May 2024) |
| FRED | Mostly re-publishes BLS/BEA | Use for **national benchmarks** and FHFA metro house prices, not as a second copy of BLS metro data |
| Greenhouse / Lever postings | Self-collected | Map job location → county → CBSA. Biased sample (only firms using these ATS), labelled as such |

Free-tools check: every source above is free. BLS, BEA, Census and FRED keys are free with no card. Nothing in this design needs a billing account. The one caution is **Power BI sharing** (see §6).

---

## 2. Exact series and tables per source

### 2.1 BLS API v2 (`https://api.bls.gov/publicAPI/v2/timeseries/data/`)

Free registered key: 50 series per request, 500 requests/day, 20 years per request **[verify limits on the BLS API page at build time]**. Our monthly pull is roughly 15 requests.

**Series ID layouts** (from [BLS series ID formats](https://www.bls.gov/help/hlpforma.htm)):

| Program | Layout | Example |
|---|---|---|
| LAUS | `LA` + seasonal(1) + area(15) + measure(2) | `LAUMT063108000000004` = unemployed, Los Angeles MSA (confirmed on FRED) |
| CES State & Area | `SM` + seasonal(1) + state(2) + area(5) + industry(8) + datatype(2) | `SMU19197802023800001` |
| JOLTS | `JT` + seasonal(1) + industry(6) + state(2) + area(5) + size(2) + element(2) + rate/level(1) | `JTU110099000000000HIL` |
| CPI-U | `CU` + seasonal(1) + periodicity(1) + area(4) + base(1) + item | `CUUR0000SA0` |

**LAUS: metro unemployment** (area code = `MT` + state FIPS + CBSA + `000000`)

| Measure code | Meaning |
|---|---|
| 03 | Unemployment rate |
| 04 | Unemployed |
| 05 | Employed |
| 06 | Labor force |

Pattern: `LAUMT{ss}{ccccc}000000{mm}`. Example: Boston (MA=25, CBSA 14460) unemployment rate → `LAUMT251446000000003` **[verify]**. For multi-state metros the state code is the metro's primary state; we read the exact ID from the `la.area` mapping file rather than constructing it by hand. Measure codes 04–06 **[verify against `la.measure`]**.
Default: not seasonally adjusted (`U`), compared year-over-year, because that is what BLS publishes for every MSA. Seasonally adjusted `LAS` metro series are used where they exist **[verify coverage]**.
4 measures × 50 metros = 200 series = 4 requests.

**CES State & Metro: jobs and earnings**

| Industry code | Supersector |
|---|---|
| 00000000 | Total nonfarm |
| 05000000 | Total private |
| 20000000 | Construction (some metros combine with mining & logging) |
| 30000000 | Manufacturing |
| 40000000 | Trade, transportation & utilities |
| 50000000 | Information |
| 55000000 | Financial activities |
| 60000000 | Professional & business services |
| 65000000 | Education & health services |
| 70000000 | Leisure & hospitality |
| 90000000 | Government |

| Data type | Meaning |
|---|---|
| 01 | All employees, thousands |
| 03 | Average hourly earnings, all employees (private) **[verify]** |
| 11 | Average weekly earnings, all employees **[verify]** |

Total nonfarm uses seasonally adjusted `SMS`; earnings are only `SMU`. Not every supersector exists for every metro, so the ingest step reads `sm.series` and keeps only IDs that exist. CES moved to the 2023 delineations with January 2025 data and dropped New England NECTAs, so Boston is now county-based like everywhere else ([BLS notice](https://www.bls.gov/sae/notices/2024/upcoming-changes-to-metropolitan-statistical-area-delineations.htm)).

**JOLTS: state substitute**

> Update (first real run, 2026-11-01): state JOLTS moved from a monthly to an **annual** release in 2026. The July 2026 release covered Jul–Dec 2025 ([BLS](https://www.bls.gov/news.release/archives/jltst_07222026.pdf)), so state rates are annual context, not a monthly signal. National JOLTS (FRED `JTSJOL`, `JTSQUR`) stays monthly.

`JTS000000{ss}00000000{EE}R`, where EE = `JO` openings, `HI` hires, `QU` quits, `LD` layoffs & discharges, `TS` total separations, and the last letter is `R` rate or `L` level **[verify state-level element coverage]**. National: `JTS000000000000000JOR`. 

**CPI-U: metro where it exists**

Series: `CUUR{area}SA0` (all items, NSA) and `CUUR{area}SA0L1E` (core).

| CPI area | Name in BLS file | CBSA it maps to |
|---|---|---|
| S11A | Boston-Cambridge-Newton | 14460 |
| S12A | New York-Newark-Jersey City | 35620 |
| S12B | Philadelphia-Camden-Wilmington | 37980 |
| S23A | Chicago-Naperville-Elgin | 16980 |
| S23B | Detroit-Warren-Dearborn | 19820 |
| S24A | Minneapolis-St. Paul-Bloomington | 33460 |
| S24B | St. Louis | 41180 |
| S35A | Washington-Arlington-Alexandria | 47900 |
| S35B | Miami-Fort Lauderdale-West Palm Beach | 33100 |
| S35C | Atlanta-Sandy Springs-Roswell | 12060 |
| S35D | Tampa-St. Petersburg-Clearwater | 45300 |
| S35E | Baltimore-Columbia-Towson | 12580 |
| S37A | Dallas-Fort Worth-Arlington | 19100 |
| S37B | Houston-The Woodlands-Sugar Land | 26420 |
| S48A | Phoenix-Mesa-Scottsdale | 38060 |
| S48B | Denver-Aurora-Lakewood | 19740 |
| S49A | Los Angeles-Long Beach-Anaheim | 31080 |
| S49B | San Francisco-Oakland-Hayward | 41860 |
| S49C | Riverside-San Bernardino-Ontario | 40140 |
| S49D | Seattle-Tacoma-Bellevue | 42660 |
| S49E | San Diego-Carlsbad | 41740 |
| S49F / S49G | Urban Hawaii / Urban Alaska | not top-50, skipped |

Area codes and names are from the official `cu.area` file. The CBSA column is my mapping by core city **[verify]**. CPI areas follow the CPI's own 2018 sample design, with older metro titles, so boundaries can differ slightly from the 2023 CBSAs. The dashboard says so.
Fallback for the other ~29 metros: division CPI `CUUR0110SA0` (New England), `0120` Middle Atlantic, `0230` East North Central, `0240` West North Central, `0350` South Atlantic, `0360` East South Central, `0370` West South Central, `0480` Mountain, `0490` Pacific. Each metro is assigned by its principal state's Census division.

### 2.2 FRED API (`https://api.stlouisfed.org/fred/series/observations`)

Used for national context lines on every chart:

| Series | What |
|---|---|
| UNRATE | U.S. unemployment rate |
| PAYEMS | U.S. nonfarm payrolls |
| CPIAUCSL | U.S. CPI-U, SA |
| JTSJOL | U.S. job openings |
| GDPC1 | U.S. real GDP |
| ATNHPIUS{cbsa}Q | FHFA all-transactions house price index by MSA, quarterly **[verify each ID]** |

Why not pull metro LAUS/CES from FRED? It is the same BLS data under different IDs, so going to BLS directly keeps one source of truth. (FRED's ALFRED vintages are a nice optional add-on to show revisions.)

### 2.3 Census ACS 2024 5-year (`https://api.census.gov/data/2024/acs/acs5`)

Geography: `for=metropolitan statistical area/micropolitan statistical area:*`

| Variable | Meaning |
|---|---|
| B01003_001E | Total population |
| B19013_001E | Median household income |
| B25064_001E | Median gross rent |
| B25077_001E | Median home value |
| B15003_001E, _022E–_025E | Pop 25+, and bachelor's / master's / professional / doctorate (for % BA+) |
| B23025_003E, _005E | Civilian labor force, unemployed |
| B17001_001E, _002E | Poverty universe, below poverty |
| B25070_001E, _007E–_010E | Renter households, rent ≥30% of income (rent burden) |

Every estimate has a matching `…M` margin-of-error variable, which we store too. Variable numbers are long-standing **[verify against the 2024 variables.json]**.

### 2.4 BEA API (`https://apps.bea.gov/api/data?datasetname=Regional`)

Because metro tables are discontinued, we pull **counties** (`GeoFips=COUNTY`) and aggregate:

| TableName | LineCode | What | Aggregate to CBSA by |
|---|---|---|---|
| CAGDP2 | 1 | GDP, current dollars, all industries | Sum of counties |
| CAGDP1 | (summary) | Real GDP, chained 2017 dollars | **Don't sum.** Use BEA's open-source geo aggregator method, or show nominal GDP only |
| CAINC1 | 1 / 2 / 3 | Personal income / population / per-capita income | Sum lines 1 and 2, recompute 3 = 1 ÷ 2 |

Line codes **[verify with `GetParameterValuesFiltered`]**. Two catches: suppressed county values ("(D)") make the metro total incomplete, so we flag those metros instead of guessing; and Connecticut moved to planning regions in 2024, which matters for Hartford if it is in the top 50. Annual, roughly 11 months lag: 2025 county data comes out **Dec 2, 2026** ([BEA schedule](https://www.bea.gov/news/schedule/)). BEA's own aggregator is described in its [technical document](https://bea.gov/sites/default/files/2026-02/geo-aggregator-technical-document.pdf).

### 2.5 BLS OEWS May 2025 (MSA file)

File `oesm25ma.zip` (xlsx inside) plus `area_definitions_m2025.xlsx` from [bls.gov/oes](https://www.bls.gov/oes/2025/may/oessrcma.htm). The AREA column is the CBSA code. Columns used: `AREA, AREA_TITLE, OCC_CODE, OCC_TITLE, TOT_EMP, JOBS_1000, LOC_QUOTIENT, A_MEAN, A_PCT10, A_PCT25, A_MEDIAN, A_PCT75, A_PCT90`.

Analyst occupations (2018 SOC):

| SOC | Title | Your target track |
|---|---|---|
| 15-2051 | Data Scientists | Data |
| 15-2041 | Statisticians | Data |
| 15-2031 | Operations Research Analysts | Ops / data |
| 15-1211 | Computer Systems Analysts | Product / data |
| 13-1111 | Management Analysts | Business |
| 13-1161 | Market Research Analysts & Marketing Specialists | Marketing |
| 13-2051 | Financial & Investment Analysts | Financial |
| 13-1081 | Logisticians | Operations |
| 29-9021 | Health Information Technologists & Medical Registrars | Healthcare |

OEWS is a once-a-year snapshot that isn't designed for year-over-year comparison, so it is a dimension of "what analysts earn here", not a time series.

### 2.6 Job postings (self-collected)

* Greenhouse Job Board API: `https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true`
* Lever Postings API: `https://api.lever.co/v0/postings/{company}?mode=json`

Both are public, documented, keyless endpoints that companies expose for their own careers pages. We keep a hand-curated `seeds/company_boards.csv` (company, ATS, token), check robots.txt, rate-limit politely, and store only job metadata (title, location, department, posted/updated date, URL). Titles are classified into the same role families as the SOC table using transparent keyword rules. Location text → Census place → county → CBSA; "Remote" is its own bucket. Caveat shown on the dashboard: this measures demand at the companies we track, not the whole market.

---

## 3. Metro crosswalk (the join key for everything)

**Universe:** the top 50 Metropolitan Statistical Areas by Census Vintage 2025 population (`cbsa-est2025-alldata.csv`, [Census](https://www.census.gov/data/tables/time-series/demo/popest/2020s-total-metro-and-micro-statistical-areas.html)), computed by script, never typed by hand. The list is frozen per run so ranks don't shift mid-year.

**Delineation:** OMB Bulletin 23-01 (July 2023), file `list1_2023.xlsx` ([Census delineation files](https://www.census.gov/geographies/reference-files/time-series/demo/metro-micro/delineation-files.html)). LAUS, CES, OEWS and ACS 2024 all use it, so most sources join on `cbsa_code` directly.

Tables:

* `dim_metro`: `cbsa_code` (PK, 5 chars), `cbsa_title`, `short_name`, `principal_state_fips`, `census_region`, `census_division`, `pop_2025`, `pop_rank`, `is_top50`
* `xwalk_metro_county`: `cbsa_code`, `county_fips` (5), `county_name`, `state_fips`, `central_outlying`, `metro_division_code`. Used for BEA aggregation and for mapping job locations.
* `xwalk_metro_source`: one row per metro per source, holding the source's own key. Examples: `laus_area_code` (MT…), `ces_state_fips + ces_area_code`, `cpi_area_code` with `cpi_geo_level` ('metro' or 'division'), `jolts_state_fips`, `oews_area`, `fhfa_fred_id`. The `geo_match` column says `exact`, `proxy` or `county_aggregate` so every chart can label its geography honestly.

---

## 4. Warehouse (free, local)

**Engine:** DuckDB, one file `warehouse/pulse.duckdb`. It runs inside Python with no server, reads Parquet natively, and works the same on a laptop and in GitHub Actions. **Transforms:** dbt Core with the `dbt-duckdb` adapter (open source). The SQL lives in `models/`, which recruiters recognise.

### raw (append-only, exactly what the source returned)
One table per source: `raw.bls_timeseries`, `raw.fred_observations`, `raw.census_acs`, `raw.bea_regional`, `raw.oews_msa`, `raw.postings_greenhouse`, `raw.postings_lever`.
Common columns: `payload` (JSON or original row), `source_url`, `request_params`, `ingested_at`, `run_id`. Raw files are also kept as Parquet in `data/raw/{source}/{run_date}/` so a run can be replayed.

### staging (typed, renamed, one grain per model)
* `stg_bls__laus`: cbsa_code, period_month, measure, value, is_preliminary, footnotes
* `stg_bls__ces`: cbsa_code, period_month, industry_code, data_type, seasonal, value
* `stg_bls__jolts_state`: state_fips, period_month, element, rate
* `stg_bls__cpi`: cpi_area_code, period_month, item, value
* `stg_fred__observations`: series_id, date, value, realtime_start
* `stg_census__acs`: cbsa_code, vintage, variable, estimate, moe
* `stg_bea__county`: county_fips, year, table, line_code, value, is_suppressed
* `stg_oews__msa`: cbsa_code, soc_code, tot_emp, a_median, a_pct10…a_pct90, loc_quotient
* `stg_postings`: posting_id, company, ats, title, role_family, location_raw, cbsa_code, is_remote, first_seen, last_seen

### marts (what the dashboard and memo read)
* Dimensions: `dim_metro`, `dim_month`, `dim_occupation` (SOC → role family), `dim_series` (every ID with source, units, SA flag, geo_match)
* `fct_labor_monthly` (metro × month): unemployment rate, labor force, employed, unemployed, nonfarm jobs, jobs YoY %, private avg hourly earnings, earnings YoY %
* `fct_industry_jobs_monthly` (metro × month × supersector)
* `fct_prices` (metro × month): CPI level, YoY %, `cpi_geo_level`, plus real wage growth = earnings YoY − CPI YoY
* `fct_metro_annual` (metro × year): nominal GDP, personal income, per-capita income, suppression flag
* `fct_metro_profile` (metro × ACS vintage): income, rent, home value, % BA+, poverty, rent burden, with MOEs
* `fct_analyst_pay` (metro × SOC, OEWS year)
* `fct_postings_monthly` (metro × month × role family): new postings, active postings, remote share
* `mart_metro_scorecard`: one wide row per metro for the latest month, which is the Power BI landing page
* `mart_memo_inputs`: biggest movers, rank changes and data-freshness notes for the one-page memo

dbt tests: `unique` and `not_null` on keys, `relationships` from every fact to `dim_metro`, and freshness checks so a stale source shows up instead of silently repeating last month.

---

## 5. Repo structure

```
us-metro-economic-pulse/
├── ingest/            # one Python module per source + shared http/retry/.env loader
│   ├── bls.py  fred.py  census_acs.py  bea.py  oews.py  postings.py  crosswalk.py
├── models/            # dbt project: staging/, marts/, seeds/, tests
├── analysis/          # notebooks + memo generator (Markdown → PDF)
├── dashboard/         # .pbix, exported Parquet/CSV marts, screenshots
├── docs/              # this design, data dictionary, source notes
├── warehouse/         # pulse.duckdb (git-ignored)
├── data/raw/          # raw Parquet (git-ignored)
├── .github/workflows/ # monthly.yml (pipeline), postings.yml (weekly scrape)
├── .env.example       # FRED_API_KEY, BLS_API_KEY, BEA_API_KEY, CENSUS_API_KEY (names only)
├── .gitignore         # .env, warehouse/, data/raw/
├── requirements.txt
└── README.md          # Khushi writes this at the end
```

---

## 6. Schedule, automation, and free-tool flags

* **Monthly run:** GitHub Actions cron a few days after BLS's monthly "Metropolitan Area Employment and Unemployment" release, which comes about a month after the reference month. The date gets set from the BLS release calendar, not guessed. Actions is free on public repos, and keys go in GitHub Actions secrets (also free).
* **Postings:** weekly Action, so first/last-seen dates mean something.
* **Persisting results:** the Action commits the small exported marts (Parquet/CSV) to `dashboard/data/` and uploads the DuckDB file as a workflow artifact. No cloud database is needed.
* **Power BI:** Power BI Desktop is free but **Windows-only**. Sharing a live public link ("Publish to web") needs the Power BI Service, a work/school sign-in, and an admin setting that BU may not allow. **Free alternatives:** commit the `.pbix` plus PDF/PNG exports, and/or mirror the same marts in **Tableau Public** or **Looker Studio** for a public URL. If you're on a Mac, Power BI Desktop would need a Windows VM, and Tableau Public is the simpler pick.
* **Memo:** generated from `mart_memo_inputs` into Markdown, then PDF, committed each month.

---

## 7. Open items before coding

1. Confirm every **[verify]** item via a dry-run ingest that prints any ID returning no data.
2. Decide whether real GDP is worth the geo-aggregator complexity, or ship nominal GDP + per-capita income only (my recommendation for v1).
3. Pick the starting list of ~50–150 company boards for postings.
4. Power BI vs Tableau Public, depending on your laptop OS.
