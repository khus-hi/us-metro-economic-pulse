{{ config(materialized='view', schema='staging') }}
-- CES State & Metro. ID layout: SM s ss ccccc iiiiiiii dd
with obs as ({{ bls_observations(source('raw', 'bls_ces')) }})
select
    series_id,
    substr(series_id, 3, 1) = 'S' as is_seasonally_adjusted,
    substr(series_id, 4, 2) as state_fips,
    substr(series_id, 6, 5) as cbsa_code,
    substr(series_id, 11, 8) as industry_code,
    substr(series_id, 19, 2) as data_type_code,
    case substr(series_id, 19, 2)
        when '01' then 'all_employees_thousands'
        when '03' then 'avg_hourly_earnings'
        when '11' then 'avg_weekly_earnings'
    end as data_type,
    month_date,
    value,
    is_preliminary,
    run_date
from obs
