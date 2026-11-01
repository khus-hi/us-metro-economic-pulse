{{ config(materialized='table', schema='marts') }}
-- Grain: one row per metro per year.
-- BEA GDP / personal income are county sums (see int_bea_metro_annual) and carry
-- an is_complete flag. ACS 5-year values sit on the ACS end year (2024 for the
-- 2020-2024 release) because a 5-year estimate is not a single-year number.
-- FHFA house prices are only used where FHFA has one index for the whole metro.
with bea as (
    select
        cbsa_code, year,
        max(case when measure = 'gdp_current_usd' then value end) as gdp_current_usd,
        max(case when measure = 'personal_income_usd' then value end) as personal_income_usd,
        max(case when measure = 'population' then value end) as bea_population,
        bool_and(is_complete) as bea_is_complete,
        min(counties_reported) as bea_counties_reported,
        max(counties_expected) as bea_counties_expected
    from {{ ref('int_bea_metro_annual') }}
    group by all
),
acs_long as (select * from {{ ref('stg_census__acs') }}),
acs as (
    select
        cbsa_code,
        acs_year as year,
        any_value(acs_vintage) as acs_vintage,
        max(case when variable = 'B01003_001' then estimate end) as acs_population,
        max(case when variable = 'B19013_001' then estimate end) as median_household_income,
        max(case when variable = 'B19013_001' then moe end) as median_household_income_moe,
        max(case when variable = 'B25064_001' then estimate end) as median_gross_rent,
        max(case when variable = 'B25077_001' then estimate end) as median_home_value,
        100 * sum(case when variable in ('B15003_022', 'B15003_023', 'B15003_024', 'B15003_025') then estimate end)
            / nullif(max(case when variable = 'B15003_001' then estimate end), 0) as pct_bachelors_or_higher,
        100 * max(case when variable = 'B23025_005' then estimate end)
            / nullif(max(case when variable = 'B23025_003' then estimate end), 0) as acs_unemployment_rate,
        100 * max(case when variable = 'B17001_002' then estimate end)
            / nullif(max(case when variable = 'B17001_001' then estimate end), 0) as poverty_rate,
        -- Share of renter households paying 30%+ of income on rent. The denominator
        -- includes households where the ratio couldn't be computed, so this slightly
        -- understates the burden; stated in the docs.
        100 * sum(case when variable in ('B25070_007', 'B25070_008', 'B25070_009', 'B25070_010') then estimate end)
            / nullif(max(case when variable = 'B25070_001' then estimate end), 0) as rent_burdened_pct
    from acs_long
    group by cbsa_code, acs_year
),
hpi as (
    select
        f.cbsa_code,
        year(o.obs_date) as year,
        avg(o.value) as fhfa_hpi_annual_avg
    from {{ ref('stg_fred__fhfa_coverage') }} f
    join {{ ref('stg_fred__observations') }} o
      on o.series_id = 'ATNHPIUS' || f.cbsa_code || 'Q'
    where f.fhfa_status = 'metro'
    group by all
    having count(o.value) = 4   -- only full years
),
spine as (
    select cbsa_code, year from bea
    union select cbsa_code, year from acs
    union select cbsa_code, year from hpi
)
select
    s.cbsa_code,
    s.year,
    b.gdp_current_usd,
    b.personal_income_usd,
    b.bea_population,
    b.personal_income_usd / nullif(b.bea_population, 0) as per_capita_income_usd,
    b.bea_is_complete,
    b.bea_counties_reported,
    b.bea_counties_expected,
    a.acs_vintage,
    a.acs_population,
    a.median_household_income,
    a.median_household_income_moe,
    a.median_gross_rent,
    a.median_home_value,
    a.pct_bachelors_or_higher,
    a.acs_unemployment_rate,
    a.poverty_rate,
    a.rent_burdened_pct,
    h.fhfa_hpi_annual_avg,
    100 * (h.fhfa_hpi_annual_avg / nullif(hp.fhfa_hpi_annual_avg, 0) - 1) as fhfa_hpi_yoy_pct
from spine s
join {{ ref('dim_metro') }} m using (cbsa_code)
left join bea b using (cbsa_code, year)
left join acs a using (cbsa_code, year)
left join hpi h using (cbsa_code, year)
left join hpi hp on hp.cbsa_code = s.cbsa_code and hp.year = s.year - 1
