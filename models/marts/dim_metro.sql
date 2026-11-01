{{ config(materialized='table', schema='marts') }}
-- One row per top-50 metro: names, geography, and flags that tell the dashboard
-- how far to trust each metro-level figure.
with counties as (
    select
        cbsa_code,
        count(*) as county_count,
        count(distinct metro_division_code) as metro_division_count
    from {{ ref('stg_metro_counties') }}
    group by cbsa_code
)
select
    m.cbsa_code,
    m.cbsa_title,
    m.short_name,
    m.principal_state,
    m.principal_state_name,
    m.principal_state_fips,
    m.census_division,
    m.census_region,
    m.population,
    m.population_vintage,
    m.pop_rank,
    m.cpi_area_code,
    m.cpi_geo_level,
    m.cpi_geo_level = 'metro' as has_metro_cpi,
    coalesce(f.fhfa_status, 'none') as fhfa_status,
    c.county_count,
    c.metro_division_count
from {{ ref('stg_metros') }} m
left join counties c using (cbsa_code)
left join {{ ref('stg_fred__fhfa_coverage') }} f using (cbsa_code)
