{{ config(materialized='view', schema='intermediate') }}
-- Sum BEA county values up to metros (BEA no longer publishes metro totals).
-- Only additive measures are summed (GDP in current dollars, personal income,
-- population). Per-capita income is recomputed from the sums, never summed.
-- counties_reported < counties_expected means some county was suppressed or
-- missing that year (e.g. Connecticut's switch to planning regions in 2024),
-- so the metro total is incomplete and flagged.
with c as (select cbsa_code, county_fips from {{ ref('stg_metro_counties') }}),
expected as (select cbsa_code, count(*) as counties_expected from c group by cbsa_code),
b as (
    select * from {{ ref('stg_bea__county') }}
    where measure in ('gdp_current_usd', 'personal_income_usd', 'population')
)
select
    c.cbsa_code,
    b.measure,
    b.year,
    sum(b.value) as value,
    count(b.value) as counties_reported,
    e.counties_expected,
    count(b.value) = e.counties_expected as is_complete
from c
join b using (county_fips)
join expected e using (cbsa_code)
group by c.cbsa_code, b.measure, b.year, e.counties_expected
