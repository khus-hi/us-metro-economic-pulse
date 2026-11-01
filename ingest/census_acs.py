"""Census ACS 2024 5-year API, every metro/micro area.

We ask for each estimate (…E) and its margin of error (…M). ACS numbers are
survey estimates, so the MOE matters: a 1-point gap between two metros can be
noise. The API caps one request at 50 variables, so we split the list.

We land all CBSAs (about 900 rows) rather than filtering to 50 here: raw stays
complete, and filtering happens in staging.
"""
from __future__ import annotations

from urllib.parse import quote

from .config import require
from .http import Client
from .landing import Manifest

YEAR = 2024
URL = f"https://api.census.gov/data/{YEAR}/acs/acs5"
GEO = "metropolitan statistical area/micropolitan statistical area:*"

VARIABLES = {
    "B01003_001": "total_population",
    "B19013_001": "median_household_income",
    "B25064_001": "median_gross_rent",
    "B25077_001": "median_home_value",
    "B15003_001": "pop_25_plus",
    "B15003_022": "bachelors",
    "B15003_023": "masters",
    "B15003_024": "professional_degree",
    "B15003_025": "doctorate",
    "B23025_003": "civilian_labor_force",
    "B23025_005": "unemployed",
    "B17001_001": "poverty_universe",
    "B17001_002": "below_poverty",
    "B25070_001": "renter_households",
    "B25070_007": "rent_30_to_34_9_pct",
    "B25070_008": "rent_35_to_39_9_pct",
    "B25070_009": "rent_40_to_49_9_pct",
    "B25070_010": "rent_50_pct_plus",
}
MAX_VARS = 49  # 50 including NAME


def requested_columns() -> list[str]:
    return [f"{v}{s}" for v in VARIABLES for s in ("E", "M")]


def run(client: Client, run_date: str) -> None:
    m = Manifest("census_acs", run_date)
    cols = requested_columns()
    for i in range(0, len(cols), MAX_VARS):
        part = cols[i:i + MAX_VARS]
        params = {"get": ",".join(["NAME", *part]), "for": GEO}
        key = require("CENSUS_API_KEY")  # Census now rejects keyless requests ("Missing Key")
        # Build the query by hand: the geography name contains spaces and a slash,
        # which Census wants as %20 and %2F rather than requests' default '+'.
        query = "&".join(f"{k}={quote(v, safe=',:*')}" for k, v in params.items())
        resp = client.get(f"{URL}?{query}&key={key}")
        try:
            rows = resp.json()  # first row is the header
        except ValueError:
            # Census answers key problems with an HTML page and HTTP 200.
            title = resp.text.split("<title>")[1].split("</title>")[0] if "<title>" in resp.text else ""
            if "Key" in title:
                raise RuntimeError(f"Census says '{title}'. Check CENSUS_API_KEY in .env and that you "
                                   "clicked the activation link in the Census email.")
            raise RuntimeError(f"Census returned non-JSON (HTTP {resp.status_code}): {resp.text[:300]!r}")
        m.write(f"acs5_{YEAR}_part{i // MAX_VARS}", rows, "json", url=URL,
                params={k: v for k, v in params.items() if k != "key"}, rows=len(rows) - 1)
    m.write("variable_labels", VARIABLES, "json")
    m.close()
