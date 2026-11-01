"""BLS Public Data API v2: LAUS, CES State & Metro, JOLTS (state), CPI.

How series IDs are chosen (interview notes):
- We never type 1,000+ IDs by hand. BLS publishes a mapping file per program
  (la.area, sm.series, jt.series) on download.bls.gov. We read those files,
  keep the rows for our 50 CBSAs, and so only ever request IDs that exist.
- LAUS:  LAU + area code (MT + state + CBSA + 000000) + measure
         (03 rate, 04 unemployed, 05 employed, 06 labor force).
- CES:   SM + S/U + state + CBSA + industry(8) + data type
         (01 all employees, 03 avg hourly earnings, 11 avg weekly earnings).
- JOLTS: no official metro data, so state-level rates for each metro's principal state.
- CPI:   metro CPI for the 21 top-50 metros BLS covers, Census-division CPI otherwise.

API limits for a free registered key: 50 series per request, 20 years per
request, 500 requests per day. We batch to fit and stop before the daily cap.
"""
from __future__ import annotations

import datetime as dt
import io
from typing import Iterable, Iterator

import pandas as pd

from .config import require
from .http import Client
from .landing import Manifest
from . import metros as metro_xwalk
from .reference import DIVISION_CPI_AREA

API_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
FILES = "https://download.bls.gov/pub/time.series"
MAX_SERIES = 50
MAX_YEARS = 20
DAILY_BUDGET = 450  # stay under the 500/day limit

LAUS_MEASURES = ("03", "04", "05", "06")
CES_INDUSTRIES = ("00000000", "05000000", "10000000", "20000000", "30000000", "40000000",
                  "50000000", "55000000", "60000000", "65000000", "70000000", "80000000", "90000000")
CES_EARNINGS = ("03", "11")
JOLTS_ELEMENTS = ("JO", "HI", "QU", "LD", "TS")
CPI_ITEMS = ("SA0", "SA0L1E")  # all items, all items less food and energy


def chunks(items: list[str], size: int = MAX_SERIES) -> Iterator[list[str]]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def year_windows(start: int, end: int, span: int = MAX_YEARS) -> list[tuple[int, int]]:
    windows, y = [], start
    while y <= end:
        windows.append((y, min(y + span - 1, end)))
        y += span
    return windows


def laus_ids(area_codes: Iterable[str]) -> list[str]:
    return [f"LAU{a}{m}" for a in area_codes for m in LAUS_MEASURES]


def cpi_ids(area_codes: Iterable[str]) -> list[str]:
    return [f"CUUR{a}{item}" for a in sorted(set(area_codes)) for item in CPI_ITEMS]


def _mapping(client: Client, m: Manifest, path: str) -> pd.DataFrame:
    url = f"{FILES}/{path}"
    content = client.get(url).content
    m.write(path.replace("/", "_"), content, "tsv", url=url)
    df = pd.read_csv(io.BytesIO(content), sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df.apply(lambda s: s.str.strip() if s.dtype == object else s)


def still_published(df: pd.DataFrame, m: Manifest, label: str) -> pd.DataFrame:
    """Mapping files also list discontinued series (e.g. a seasonally adjusted
    version BLS stopped producing). Asking for those returns 'Series does not
    exist', so keep only series whose last observation is recent."""
    recent = pd.to_numeric(df["end_year"], errors="coerce") >= dt.date.today().year - 1
    if (~recent).any():
        m.warn(f"{label}: skipped {int((~recent).sum())} discontinued series")
    return df[recent]


def discover(client: Client, m: Manifest, metros: pd.DataFrame) -> dict[str, list[str]]:
    cbsas = set(metros["cbsa_code"])

    la = _mapping(client, m, "la/la.area")
    la_msa = la[(la["area_type_code"] == "B") & la["area_code"].str[4:9].isin(cbsas)]
    found = set(la_msa["area_code"].str[4:9])
    if cbsas - found:
        m.warn(f"LAUS: no MSA area code for {sorted(cbsas - found)}")

    sm = _mapping(client, m, "sm/sm.series")
    sm = sm[sm["area_code"].isin(cbsas)]
    # Interstate metros can appear under more than one state; keep the principal state's copy.
    principal = dict(zip(metros["cbsa_code"], metros["principal_state_fips"]))
    sm = sm[sm["state_code"] == sm["area_code"].map(principal)]
    jobs = sm[sm["industry_code"].isin(CES_INDUSTRIES) & (sm["data_type_code"] == "01")]
    pay = sm[(sm["industry_code"] == "05000000") & sm["data_type_code"].isin(CES_EARNINGS)]
    ces = still_published(pd.concat([jobs, pay]), m, "CES")
    no_ces = cbsas - set(ces["area_code"])
    if no_ces:
        m.warn(f"CES: no series under principal state for {sorted(no_ces)}")

    jt = _mapping(client, m, "jt/jt.series")
    states = set(metros["principal_state_fips"])
    jolts = jt[(jt["seasonal"] == "S") & (jt["industry_code"] == "000000")
               & (jt["state_code"].isin(states | {"00"})) & (jt["area_code"] == "00000")
               & (jt["sizeclass_code"] == "00") & (jt["dataelement_code"].isin(JOLTS_ELEMENTS))
               & (jt["ratelevel_code"] == "R")]
    jolts = still_published(jolts, m, "JOLTS")

    cpi_areas = set(metros["cpi_area_code"]) | {"0000"}
    return {
        "laus": laus_ids(la_msa["area_code"]),
        "ces": sorted(ces["series_id"]),
        "jolts": sorted(jolts["series_id"]),
        "cpi": cpi_ids(cpi_areas),
    }


def fetch(client: Client, m: Manifest, program: str, series: list[str],
          start_year: int, end_year: int, budget: list[int]) -> None:
    key = require("BLS_API_KEY")
    for w_start, w_end in year_windows(start_year, end_year):
        for i, batch in enumerate(chunks(series)):
            if budget[0] >= DAILY_BUDGET:
                m.warn("Stopped: reached daily BLS request budget; re-run tomorrow.")
                return
            payload = {"seriesid": batch, "startyear": str(w_start), "endyear": str(w_end),
                       "registrationkey": key}
            body = client.post(API_URL, json=payload).json()
            budget[0] += 1
            if body.get("status") != "REQUEST_SUCCEEDED":
                m.warn(f"{program} batch {i} {w_start}-{w_end}: {body.get('status')} {body.get('message')}")
            for msg in body.get("message", []):
                m.warn(f"{program}: {msg}")
            rows = sum(len(s.get("data", [])) for s in body.get("Results", {}).get("series", []))
            m.write(f"{program}_{w_start}-{w_end}_{i:03d}", body, "json", url=API_URL,
                    params={"seriesid": batch, "startyear": w_start, "endyear": w_end}, rows=rows)


def run(client: Client, run_date: str, start_year: int, end_year: int,
        programs: Iterable[str] = ("laus", "ces", "jolts", "cpi")) -> None:
    metros = metro_xwalk.load()
    m = Manifest("bls", run_date)
    ids = discover(client, m, metros)
    m.write("series_requested", ids, "json")
    budget = [0]
    for program in programs:
        fetch(client, m, program, ids[program], start_year, end_year, budget)
    m.close()


__all__ = ["run", "laus_ids", "cpi_ids", "chunks", "year_windows", "DIVISION_CPI_AREA"]
