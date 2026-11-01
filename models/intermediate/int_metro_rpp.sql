{{ config(materialized='view', schema='intermediate') }}
-- One cost-of-living value per top-50 metro: BEA's metro RPP when BEA publishes
-- one (matching the current CBSA code or its pre-2023 code), otherwise the
-- principal state's RPP. Latest year available for each.
with metros as (select cbsa_code, principal_state_fips from {{ ref('stg_metros') }}),
rpp as (select * from {{ ref('stg_bea__rpp') }}),
metro_latest as (
    select m.cbsa_code, r.rpp, r.year
    from metros m
    left join {{ ref('cbsa_legacy_codes') }} l using (cbsa_code)
    join rpp r on r.geo_level = 'metro' and r.geo_fips in (m.cbsa_code, l.legacy_cbsa_code)
    qualify row_number() over (partition by m.cbsa_code order by r.year desc, (r.geo_fips = m.cbsa_code) desc) = 1
),
state_latest as (
    select m.cbsa_code, r.rpp, r.year
    from metros m
    join rpp r on r.geo_level = 'state' and r.state_fips = m.principal_state_fips
    qualify row_number() over (partition by m.cbsa_code order by r.year desc) = 1
)
select
    m.cbsa_code,
    coalesce(ml.rpp, sl.rpp) as rpp,
    coalesce(ml.year, sl.year) as rpp_year,
    case when ml.rpp is not null then 'metro' when sl.rpp is not null then 'state' end as rpp_geo_level
from metros m
left join metro_latest ml using (cbsa_code)
left join state_latest sl using (cbsa_code)
