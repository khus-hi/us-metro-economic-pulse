{{ config(materialized='view', schema='staging') }}
-- BEA county GDP and personal income. BEA stopped publishing metro totals in 2026,
-- so counties are summed to metros in intermediate/int_bea_metro_annual.
-- "(D)" = suppressed to protect confidentiality, "(NA)" = not available: both NULL + flag.
-- UNIT_MULT is a power of ten (3 = thousands), so value_usd is in plain units.
with files as (
    select
        regexp_extract(filename, '(CA[A-Z0-9]+)_line(\d+)\.json$', 1) as table_name,
        regexp_extract(filename, '(CA[A-Z0-9]+)_line(\d+)\.json$', 2) as line_code,
        content::json as j,
        {{ run_date_from('filename') }} as run_date
    from {{ source('raw', 'bea') }}
),
rows_ as (
    select table_name, line_code, run_date, unnest(from_json(j -> '$.BEAAPI.Results.Data', '["json"]')) as d
    from files
),
typed as (
    select
        table_name,
        line_code,
        d ->> 'GeoFips' as county_fips,
        d ->> 'GeoName' as county_name,
        cast(d ->> 'TimePeriod' as integer) as year,
        d ->> 'CL_UNIT' as unit,
        try_cast(d ->> 'UNIT_MULT' as integer) as unit_mult,
        d ->> 'DataValue' as raw_value,
        run_date
    from rows_
)
select
    table_name,
    line_code,
    case
        when table_name = 'CAGDP2' and line_code = '1' then 'gdp_current_usd'
        when table_name = 'CAINC1' and line_code = '1' then 'personal_income_usd'
        when table_name = 'CAINC1' and line_code = '2' then 'population'
        when table_name = 'CAINC1' and line_code = '3' then 'per_capita_income_usd'
    end as measure,
    county_fips,
    county_name,
    year,
    unit,
    try_cast(replace(raw_value, ',', '') as double) * power(10, coalesce(unit_mult, 0)) as value,
    try_cast(replace(raw_value, ',', '') as double) is null as is_suppressed,
    raw_value,
    run_date
from typed
qualify row_number() over (partition by table_name, line_code, county_fips, year order by run_date desc) = 1
