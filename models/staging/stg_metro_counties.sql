{{ config(materialized='view', schema='staging') }}
-- County membership of each top-50 metro (OMB Bulletin 23-01).
select
    cbsa_code,
    lpad(county_fips, 5, '0') as county_fips,
    county_name,
    state_name,
    central_outlying,
    nullif(metro_division_code, '') as metro_division_code
from {{ source('reference', 'metro_counties') }}
