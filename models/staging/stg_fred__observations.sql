{{ config(materialized='view', schema='staging') }}
-- FRED observations: national benchmarks + FHFA house price indexes.
-- FRED marks missing values with '.', which becomes NULL here.
with files as (
    select
        regexp_extract(filename, '([^/]+)\.json$', 1) as series_id,
        content::json as j,
        {{ run_date_from('filename') }} as run_date
    from {{ source('raw', 'fred') }}
    where filename not like '%/\_manifest.json' escape '\'
      and filename not like '%/fhfa\_coverage.json' escape '\'
),
obs as (
    select series_id, run_date, unnest(from_json(j -> '$.observations', '["json"]')) as o
    from files
)
select
    series_id,
    cast(o ->> 'date' as date) as obs_date,
    try_cast(o ->> 'value' as double) as value,
    run_date
from obs
qualify row_number() over (partition by series_id, obs_date order by run_date desc) = 1
