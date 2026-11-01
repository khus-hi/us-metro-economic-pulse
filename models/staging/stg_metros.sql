{{ config(materialized='view', schema='staging') }}
-- Top-50 metros from the crosswalk, with state names and Census region attached.
select
    m.cbsa_code,
    m.cbsa_title,
    split_part(m.cbsa_title, '-', 1) as short_name,
    m.principal_state,
    m.principal_state_fips,
    s.state_name as principal_state_name,
    cast(m.census_division as integer) as census_division,
    s.census_region,
    cast(m.population as bigint) as population,
    cast(m.population_vintage as integer) as population_vintage,
    cast(m.pop_rank as integer) as pop_rank,
    m.cpi_area_code,
    m.cpi_geo_level
from {{ source('reference', 'metros') }} m
left join {{ ref('state_names') }} s on m.principal_state = s.postal
