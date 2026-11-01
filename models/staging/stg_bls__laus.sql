{{ config(materialized='view', schema='staging') }}
-- LAUS metro labor force. ID layout: LA U MT ss ccccc 000000 mm
--   positions 8-12 = CBSA code, 19-20 = measure.
with obs as ({{ bls_observations(source('raw', 'bls_laus')) }})
select
    series_id,
    substr(series_id, 8, 5) as cbsa_code,
    substr(series_id, 19, 2) as measure_code,
    case substr(series_id, 19, 2)
        when '03' then 'unemployment_rate'
        when '04' then 'unemployed'
        when '05' then 'employed'
        when '06' then 'labor_force'
    end as measure,
    month_date,
    value,
    is_preliminary,
    run_date
from obs
