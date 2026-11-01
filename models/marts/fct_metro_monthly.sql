{{ config(materialized='table', schema='marts') }}
-- Grain: one row per metro per month.
-- Jobs and unemployment are metro-level. CPI is metro-level for 21 metros and the
-- Census-division CPI otherwise (cpi_geo_level says which). JOLTS rates are for the
-- metro's principal state. Year-over-year changes compare the same month a year
-- earlier, which also removes seasonality from not-seasonally-adjusted series.
with spine as (
    select distinct cbsa_code, month_date from {{ ref('stg_bls__laus') }}
    union
    select distinct cbsa_code, month_date from {{ ref('stg_bls__ces') }}
),
metros as (select * from {{ ref('dim_metro') }}),
laus as (
    select
        cbsa_code, month_date,
        max(case when measure = 'unemployment_rate' then value end) as unemployment_rate,
        max(case when measure = 'labor_force' then value end) as labor_force,
        max(case when measure = 'employed' then value end) as employed,
        max(case when measure = 'unemployed' then value end) as unemployed,
        bool_or(is_preliminary) as laus_is_preliminary
    from {{ ref('stg_bls__laus') }}
    group by all
),
ces as (
    select
        cbsa_code, month_date,
        max(case when industry_code = '00000000' and data_type_code = '01' and is_seasonally_adjusted then value end) as jobs_sa,
        max(case when industry_code = '00000000' and data_type_code = '01' and not is_seasonally_adjusted then value end) as jobs_nsa,
        max(case when industry_code = '05000000' and data_type_code = '03' then value end) as avg_hourly_earnings,
        max(case when industry_code = '05000000' and data_type_code = '11' then value end) as avg_weekly_earnings
    from {{ ref('stg_bls__ces') }}
    group by all
),
cpi as (
    select cpi_area_code, month_date, max(case when item = 'all_items' then value end) as cpi_all_items
    from {{ ref('stg_bls__cpi') }}
    group by all
),
jolts as (
    select
        state_fips, month_date,
        max(case when element = 'job_openings_rate' then value end) as state_job_openings_rate,
        max(case when element = 'hires_rate' then value end) as state_hires_rate,
        max(case when element = 'quits_rate' then value end) as state_quits_rate,
        max(case when element = 'layoffs_rate' then value end) as state_layoffs_rate
    from {{ ref('stg_bls__jolts_state') }}
    group by all
),
us as (
    select
        obs_date as month_date,
        max(case when series_id = 'UNRATE' then value end) as us_unemployment_rate,
        max(case when series_id = 'CPIAUCSL' then value end) as us_cpi
    from {{ ref('stg_fred__observations') }}
    where series_id in ('UNRATE', 'CPIAUCSL')
    group by all
),
base as (
    select
        s.cbsa_code,
        s.month_date,
        l.unemployment_rate, l.labor_force, l.employed, l.unemployed, l.laus_is_preliminary,
        coalesce(c.jobs_sa, c.jobs_nsa) as nonfarm_jobs_thousands,
        c.jobs_sa is not null as nonfarm_jobs_is_sa,
        c.jobs_nsa,
        c.avg_hourly_earnings,
        c.avg_weekly_earnings,
        p.cpi_all_items,
        m.cpi_area_code,
        m.cpi_geo_level,
        j.state_job_openings_rate, j.state_hires_rate, j.state_quits_rate, j.state_layoffs_rate,
        u.us_unemployment_rate,
        u.us_cpi
    from spine s
    join metros m using (cbsa_code)
    left join laus l using (cbsa_code, month_date)
    left join ces c using (cbsa_code, month_date)
    left join cpi p on p.cpi_area_code = m.cpi_area_code and p.month_date = s.month_date
    left join jolts j on j.state_fips = m.principal_state_fips and j.month_date = s.month_date
    left join us u on u.month_date = s.month_date
)
select
    b.*,
    100 * (coalesce(b.jobs_nsa, b.nonfarm_jobs_thousands) / nullif(coalesce(y.jobs_nsa, y.nonfarm_jobs_thousands), 0) - 1) as nonfarm_jobs_yoy_pct,
    100 * (b.avg_hourly_earnings / nullif(y.avg_hourly_earnings, 0) - 1) as avg_hourly_earnings_yoy_pct,
    100 * (b.cpi_all_items / nullif(y.cpi_all_items, 0) - 1) as cpi_yoy_pct,
    100 * (b.us_cpi / nullif(y.us_cpi, 0) - 1) as us_cpi_yoy_pct,
    -- Real wage growth: nominal earnings growth minus local (or regional) inflation.
    100 * (b.avg_hourly_earnings / nullif(y.avg_hourly_earnings, 0) - 1)
      - 100 * (b.cpi_all_items / nullif(y.cpi_all_items, 0) - 1) as real_wage_growth_pct
from base b
left join base y
  on y.cbsa_code = b.cbsa_code
 and y.month_date = cast(b.month_date - interval 12 month as date)
