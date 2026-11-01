{{ config(materialized='table', schema='marts') }}
-- Grain: one row per posting per location it maps to. A posting listed in two
-- metros appears twice (once per metro); unmapped postings appear once with a
-- NULL cbsa_code and a location_class saying why. Count distinct job_key for
-- "how many postings", and group by cbsa_code for "postings by metro".
select
    l.job_key,
    l.cbsa_code,
    coalesce(l.cbsa_code, l.location_class) as location_key,
    l.location_class,
    p.company,
    p.title,
    p.role_family,
    p.location,
    p.is_remote,
    p.posted_date,
    p.first_seen,
    p.last_seen,
    p.is_open,
    datediff('day', p.first_seen, p.last_seen) + 1 as days_listed_so_far,
    p.tools,
    coalesce(len(string_split(p.tools, ';')), 0) as tool_count,
    p.url
from {{ ref('int_postings_metro') }} l
join {{ ref('stg_postings') }} p using (job_key)
