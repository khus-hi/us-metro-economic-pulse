{{ config(materialized='view', schema='staging') }}
-- BEA Regional Price Parities, all items. 100 = US average price level, so
-- 110 means prices ~10% above average. MARPP = metros, SARPP = states.
-- A table BEA no longer serves comes back with an Error and no Data rows,
-- which simply yields no rows here.
with files as (
    select
        regexp_extract(filename, 'RPP_([A-Z]+)\.json$', 1) as table_name,
        content::json as j,
        {{ run_date_from('filename') }} as run_date
    from {{ source('raw', 'bea_rpp') }}
),
rows_ as (
    select table_name, run_date, unnest(from_json(coalesce(j -> '$.BEAAPI.Results.Data', '[]'), '["json"]')) as d
    from files
)
select
    case table_name when 'MARPP' then 'metro' when 'SARPP' then 'state' end as geo_level,
    d ->> 'GeoFips' as geo_fips,
    case when table_name = 'SARPP' then left(d ->> 'GeoFips', 2) end as state_fips,
    d ->> 'GeoName' as geo_name,
    cast(d ->> 'TimePeriod' as integer) as year,
    try_cast(replace(d ->> 'DataValue', ',', '') as double) as rpp,
    run_date
from rows_
where try_cast(replace(d ->> 'DataValue', ',', '') as double) is not null
qualify row_number() over (partition by table_name, d ->> 'GeoFips', d ->> 'TimePeriod' order by run_date desc) = 1
