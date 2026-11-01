"""Metro crosswalk: which 50 metros, and which counties are in each.

Step 1. Download Census Vintage 2025 CBSA population estimates and rank the
        Metropolitan Statistical Areas by the latest population estimate.
Step 2. Download the OMB Bulletin 23-01 delineation file (list1_2023.xlsx),
        which lists every county in every CBSA.
Step 3. Write two reference tables that every other extractor reads:
        data/reference/metros_top50.csv and data/reference/metro_counties.csv.

Nothing is hard-coded: if Census publishes a new vintage, change the URL
and the top 50 is recomputed.
"""
from __future__ import annotations

import io

import pandas as pd

from .config import REFERENCE_DIR
from .http import Client
from .landing import Manifest
from .reference import STATES, cpi_area_for, principal_state

POP_URL = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/metro/totals/cbsa-est2025-alldata.csv"
DELINEATION_URL = ("https://www2.census.gov/programs-surveys/metro-micro/geographies/"
                   "reference-files/2023/delineation-files/list1_2023.xlsx")
TOP_N = 50

METROS_FILE = REFERENCE_DIR / "metros_top50.csv"
COUNTIES_FILE = REFERENCE_DIR / "metro_counties.csv"


def _read_delineation(content: bytes) -> pd.DataFrame:
    """The xlsx has title rows above the header and footnotes below the data."""
    probe = pd.read_excel(io.BytesIO(content), header=None, dtype=str)
    header_row = probe.index[probe.apply(lambda r: r.astype(str).str.strip().eq("CBSA Code").any(), axis=1)][0]
    df = pd.read_excel(io.BytesIO(content), header=header_row, dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    return df[df["FIPS County Code"].notna() & df["CBSA Code"].str.fullmatch(r"\d{5}", na=False)]


def build(client: Client, run_date: str) -> pd.DataFrame:
    m = Manifest("crosswalk", run_date)

    pop_bytes = client.get(POP_URL).content
    m.write("cbsa-est2025-alldata", pop_bytes, "csv", url=POP_URL)
    pop = pd.read_csv(io.BytesIO(pop_bytes), dtype=str, encoding="latin-1")
    pop_cols = sorted(c for c in pop.columns if c.startswith("POPESTIMATE") and c[-4:].isdigit())
    latest = pop_cols[-1]
    msas = pop[pop["LSAD"] == "Metropolitan Statistical Area"].copy()
    msas["pop"] = msas[latest].astype(int)
    msas = msas.sort_values("pop", ascending=False).head(TOP_N).reset_index(drop=True)
    msas["pop_rank"] = msas.index + 1

    del_bytes = client.get(DELINEATION_URL).content
    m.write("list1_2023", del_bytes, "xlsx", url=DELINEATION_URL)
    counties = _read_delineation(del_bytes)

    rows = []
    for r in msas.itertuples():
        st = principal_state(r.NAME)
        cpi_area, cpi_level = cpi_area_for(r.CBSA, st)
        rows.append({
            "cbsa_code": r.CBSA,
            "cbsa_title": r.NAME,
            "principal_state": st,
            "principal_state_fips": STATES[st][0],
            "census_division": STATES[st][1],
            "population": r.pop,
            "population_vintage": latest.replace("POPESTIMATE", ""),
            "pop_rank": r.pop_rank,
            "cpi_area_code": cpi_area,
            "cpi_geo_level": cpi_level,
        })
    metros = pd.DataFrame(rows)

    c = counties[counties["CBSA Code"].isin(metros["cbsa_code"])]
    metro_counties = pd.DataFrame({
        "cbsa_code": c["CBSA Code"],
        "county_fips": c["FIPS State Code"].str.zfill(2) + c["FIPS County Code"].str.zfill(3),
        "county_name": c["County/County Equivalent"],
        "state_name": c["State Name"],
        "central_outlying": c["Central/Outlying County"],
        "metro_division_code": c["Metropolitan Division Code"],
    })

    missing = set(metros["cbsa_code"]) - set(metro_counties["cbsa_code"])
    if missing:
        m.warn(f"CBSAs in population file but not in delineation file: {sorted(missing)}")

    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    metros.to_csv(METROS_FILE, index=False)
    metro_counties.to_csv(COUNTIES_FILE, index=False)
    m.files.append({"file": str(METROS_FILE), "rows": len(metros)})
    m.files.append({"file": str(COUNTIES_FILE), "rows": len(metro_counties)})
    m.close()
    return metros


def load() -> pd.DataFrame:
    if not METROS_FILE.exists():
        raise FileNotFoundError("Run `python -m ingest run crosswalk` first.")
    return pd.read_csv(METROS_FILE, dtype={"cbsa_code": str, "principal_state_fips": str})


def load_counties() -> pd.DataFrame:
    return pd.read_csv(COUNTIES_FILE, dtype=str)
