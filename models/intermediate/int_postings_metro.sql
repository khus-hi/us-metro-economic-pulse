{{ config(materialized='view', schema='intermediate') }}
-- Map each posting's free-text location to top-50 metros.
--
-- A location like "New York, NY; San Francisco, California, United States" is split
-- into segments, and each segment is matched to a metro when it contains one of the
-- metro's principal city names (from the CBSA title) AND one of the metro's states
-- (postal code or full name). A bare city with no state ("Austin") also matches,
-- unless the city name is also a state name ("Washington"). A short alias list in
-- reference/location_aliases.csv handles things like "NYC" and "Bay Area".
--
-- Postings that match no metro are kept, with location_class explaining why:
--   remote_us   - remote and US (or no country given)
--   non_us      - every segment points outside the US
--   us_unmapped - in the US but not in a top-50 metro
--   unknown     - not enough information (e.g. a bare city name outside the top 50)
with p as (
    select job_key, coalesce(location, '') as location, is_remote from {{ ref('stg_postings') }}
),
seg as (
    select job_key, is_remote, trim(s) as segment
    from p, unnest(regexp_split_to_array(location, '\s*(;|\|| or )\s*')) as t(s)
    where trim(s) <> ''
),
states as (select postal, state_name from {{ ref('state_names') }}),
metro_states as (
    select m.cbsa_code, trim(st) as postal, s.state_name
    from {{ ref('stg_metros') }} m,
         unnest(string_split(trim(split_part(m.cbsa_title, ',', 2)), '-')) as t(st)
    join states s on s.postal = trim(st)
),
cities as (
    select distinct m.cbsa_code, trim(c) as city
    from {{ ref('stg_metros') }} m,
         unnest(regexp_split_to_array(split_part(m.cbsa_title, ',', 1), '-|/')) as t(c)
    where length(trim(c)) >= 3
),
city_hits as (
    select distinct s.job_key, s.segment, c.cbsa_code
    from seg s
    join cities c on contains(lower(s.segment), lower(c.city))
    where exists (
            select 1 from metro_states ms
            where ms.cbsa_code = c.cbsa_code
              and (regexp_matches(s.segment, '\b' || ms.postal || '\b')
                   or contains(lower(s.segment), lower(ms.state_name)))
          )
       or (s.segment not like '%,%'
           and lower(c.city) not in (select lower(state_name) from states))
),
alias_hits as (
    select distinct s.job_key, s.segment, a.cbsa_code
    from seg s
    join {{ ref('location_aliases') }} a on contains(lower(s.segment), lower(a.pattern))
    where a.cbsa_code in (select cbsa_code from {{ ref('stg_metros') }})
),
hits as (
    select job_key, cbsa_code from city_hits
    union
    select job_key, cbsa_code from alias_hits
),
us_flags as (
    select
        s.job_key,
        bool_or(
            regexp_matches(s.segment, '(?i)united states|\busa\b|\bu\.s\.|\bUS\b')
            or exists (select 1 from states st
                       where regexp_matches(s.segment, ',\s*' || st.postal || '\b')
                          or contains(lower(s.segment), lower(st.state_name)))
        ) as has_us_marker,
        bool_or(regexp_matches(s.segment, '(?i)^(remote|anywhere|fully remote)$')) as is_bare_remote
    from seg s
    group by s.job_key
),
unmatched as (
    select
        p.job_key,
        cast(null as varchar) as cbsa_code,
        case
            when p.is_remote and (coalesce(u.has_us_marker, false) or coalesce(u.is_bare_remote, true)) then 'remote_us'
            when coalesce(u.has_us_marker, false) then 'us_unmapped'
            -- "City, Country" or "Remote <country>" with no US marker
            when p.location like '%,%' or p.is_remote then 'non_us'
            else 'unknown'   -- e.g. a bare city name we don't recognise
        end as location_class
    from p
    left join us_flags u using (job_key)
    where p.job_key not in (select job_key from hits)
)
select job_key, cbsa_code, 'metro' as location_class from hits
union all
select job_key, cbsa_code, location_class from unmatched
