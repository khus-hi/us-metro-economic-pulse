{{ config(materialized='table', schema='marts') }}
-- Grain: one row per posting x location x tool mentioned.
-- Answers "which tools do analyst postings in Boston ask for?" with a simple group by.
select
    f.job_key,
    f.cbsa_code,
    f.location_key,
    f.location_class,
    f.role_family,
    f.is_open,
    trim(t.tool) as tool
from {{ ref('fct_postings') }} f,
     unnest(string_split(f.tools, ';')) as t(tool)
where f.tools is not null and trim(t.tool) <> ''
