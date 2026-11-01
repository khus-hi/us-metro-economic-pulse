{{ config(materialized='view', schema='staging') }}
-- CPI-U, not seasonally adjusted. ID layout: CU U R aaaa S item
-- Bimonthly metro areas only have every other month; we do not fill the gaps.
with obs as ({{ bls_observations(source('raw', 'bls_cpi')) }})
select
    series_id,
    substr(series_id, 5, 4) as cpi_area_code,
    substr(series_id, 9) as item_code,
    case substr(series_id, 9) when 'SA0' then 'all_items' when 'SA0L1E' then 'core' end as item,
    month_date,
    value,
    is_preliminary,
    run_date
from obs
