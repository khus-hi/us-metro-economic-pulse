{{ config(materialized='view', schema='staging') }}
-- Which FHFA house price series exist for each metro, and whether they cover the whole metro.
--   metro          = one index for the whole CBSA
--   all_divisions  = every metropolitan division has its own index
--   partial / none = do not use as a metro-wide figure
with f as (
    select content::json as j, {{ run_date_from('filename') }} as run_date
    from {{ source('raw', 'fred') }}
    where filename like '%/fhfa\_coverage.json' escape '\'
    qualify row_number() over (order by run_date desc) = 1
),
k as (select j, run_date, unnest(json_keys(j)) as cbsa_code from f)
select
    cbsa_code,
    json_extract_string(j, '$."' || cbsa_code || '".status') as fhfa_status,
    from_json(json_extract(j, '$."' || cbsa_code || '".found'), '["varchar"]') as fhfa_series_ids,
    run_date
from k
