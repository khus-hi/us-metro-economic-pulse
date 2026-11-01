# Ingest layer

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # paste your 4 free keys + your email
python -m ingest run all      # crosswalk first, then every source
python -m ingest sample       # a few rows from each latest raw run
pytest                        # unit tests + checks on the real raw files
```

Raw files land in `data/raw/{source}/{run_date}/`, one `_manifest.json` per source and run (URLs, params with keys removed, row counts, warnings). `data/` is git-ignored because it can always be re-pulled.

## What each module does

| Module | Source | Pulls | Notes |
|---|---|---|---|
| `metros.py` | Census PEP Vintage 2025 + OMB 23-01 delineation | Top 50 MSAs by population, their counties | Everything else joins on `cbsa_code` |
| `bls.py` | BLS API v2 | LAUS (4 measures), CES (13 supersectors + private earnings), state JOLTS rates, CPI | IDs discovered from BLS mapping files; 50 series/request, 20 years/request, stops before 500 requests/day |
| `fred.py` | FRED | National benchmarks + FHFA metro HPI | Offset pagination; unknown IDs logged as warnings |
| `census_acs.py` | ACS 2024 5-year | 18 variables × (estimate, MOE), all CBSAs | API when `CENSUS_API_KEY` is set; otherwise the keyless table-based Summary File, streamed and filtered to CBSA rows |
| `bea.py` | BEA Regional | County GDP (CAGDP2) and personal income (CAINC1) | BEA dropped metro tables in 2026; counties get summed in `models/` |
| `oews.py` | OEWS May 2025 zip | Analyst occupations × 50 metros | Raw zip kept; filtered CSV for convenience |
| `postings.py` | Greenhouse / Lever public boards | All jobs for companies in `seeds/company_boards.csv` | Lever paged with skip/limit |

## Interview talking points

- **Retries vs. errors.** 429 and 5xx responses are retried with exponential backoff and honour `Retry-After`. 4xx responses are not, because retrying can't fix a bad ID. Those are logged in the manifest instead.
- **Rate limits.** There is a per-host minimum gap between calls, set below each provider's published limit. BEA locks a key for an hour if you exceed its limit.
- **Replayability.** Raw responses are stored untouched with a run date, so transforms can be re-run without calling the APIs again.
- **Fail loud, not silent.** The tests check that every metro is present and every series is recent, so a metro dropping out or a series going stale fails a test rather than quietly showing old numbers.
