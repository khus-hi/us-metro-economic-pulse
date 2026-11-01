{{ config(materialized='view', schema='staging') }}
-- State JOLTS rates (BLS publishes JOLTS for states, not metros; annual release since 2026).
-- ID layout: JT s iiiiii ss aaaaa zz ee r
with obs as ({{ bls_observations(source('raw', 'bls_jolts')) }})
select
    series_id,
    substr(series_id, 10, 2) as state_fips,
    substr(series_id, 19, 2) as element_code,
    case substr(series_id, 19, 2)
        when 'JO' then 'job_openings_rate'
        when 'HI' then 'hires_rate'
        when 'QU' then 'quits_rate'
        when 'LD' then 'layoffs_rate'
        when 'TS' then 'separations_rate'
    end as element,
    month_date,
    value,
    is_preliminary,
    run_date
from obs
