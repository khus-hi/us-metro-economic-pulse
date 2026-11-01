"""FRED API: national benchmark series + FHFA house price index by metro.

Why FRED only for these: FRED re-publishes BLS metro data under different IDs.
Pulling metro jobs/unemployment straight from BLS keeps one source of truth;
FRED adds the national lines and FHFA's metro house prices.

Pagination: /fred/series/observations returns at most `limit` rows
(max 100,000) and a `count`; we keep requesting with a larger `offset`
until we have them all.
"""
from __future__ import annotations

import requests

from .config import require
from .http import Client
from .landing import Manifest
from . import metros as metro_xwalk

URL = "https://api.stlouisfed.org/fred/series/observations"
NATIONAL = ("UNRATE", "PAYEMS", "CPIAUCSL", "CPILFESL", "JTSJOL", "JTSQUR", "GDPC1", "GDP")
PAGE = 100_000


def fhfa_id(code: str) -> str:
    """FHFA all-transactions HPI, quarterly, by MSA or metropolitan division code."""
    return f"ATNHPIUS{code}Q"


# FHFA still uses some pre-2023 codes. Extra IDs to try, keyed by 2023 CBSA.
# Each one is only accepted if FRED actually has it. [verify on each run]
LEGACY_FHFA = {
    "17410": ["17460"],           # Cleveland, OH (was Cleveland-Elyria 17460)
    "47900": ["47894"],           # Washington DC division under the old delineation
    "19820": ["47664"],           # Detroit metro's Warren-Troy-Farmington Hills division
}


def fhfa_candidates(counties) -> dict[str, list[str]]:
    """Every FHFA ID worth trying for each metro: its 2023 divisions, the
    whole-metro code, and known legacy codes. FHFA publishes metros split into
    metropolitan divisions only per division, and some codes predate 2023."""
    out = {}
    for cbsa, grp in counties.groupby("cbsa_code"):
        divs = sorted(grp["metro_division_code"].dropna().unique())
        out[cbsa] = [fhfa_id(c) for c in [*divs, cbsa, *LEGACY_FHFA.get(cbsa, [])]]
    return out


def fhfa_ids(counties) -> list[str]:
    return [i for ids in fhfa_candidates(counties).values() for i in ids]


def observations(client: Client, series_id: str, start: str) -> dict:
    params = {"series_id": series_id, "api_key": require("FRED_API_KEY"), "file_type": "json",
              "observation_start": start, "limit": PAGE, "offset": 0}
    first = client.get(URL, params=params).json()
    obs = list(first.get("observations", []))
    while len(obs) < int(first.get("count", 0)):
        params["offset"] = len(obs)
        obs += client.get(URL, params=params).json().get("observations", [])
    first["observations"] = obs
    return first


def _fetch(client: Client, m: Manifest, sid: str, start_year: int) -> bool:
    try:
        body = observations(client, sid, f"{start_year}-01-01")
    except requests.HTTPError as e:
        if e.response.status_code == 400:  # FRED's answer for an ID that does not exist
            return False
        raise
    m.write(sid, body, "json", url=URL, params={"series_id": sid, "observation_start": start_year},
            rows=len(body["observations"]))
    return True


def run(client: Client, run_date: str, start_year: int) -> None:
    m = Manifest("fred", run_date)
    for sid in NATIONAL:
        if not _fetch(client, m, sid, start_year):
            m.warn(f"{sid}: series does not exist")

    counties = metro_xwalk.load_counties()
    divisions = {c: sorted(g["metro_division_code"].dropna().unique()) for c, g in counties.groupby("cbsa_code")}
    coverage = {}
    for cbsa, ids in fhfa_candidates(counties).items():
        found = [sid for sid in ids if _fetch(client, m, sid, start_year)]
        div_ids = {fhfa_id(d) for d in divisions[cbsa]}
        whole = fhfa_id(cbsa) in found
        status = ("metro" if whole or not div_ids and found
                  else "all_divisions" if div_ids and div_ids <= set(found)
                  else "partial" if found else "none")
        coverage[cbsa] = {"status": status, "found": found}
    for status in ("none", "partial"):
        bad = sorted(c for c, v in coverage.items() if v["status"] == status)
        if bad:
            # 'partial' matters: e.g. only one division of a split metro would
            # misrepresent the whole metro, so models/ must not use it as-is.
            m.warn(f"FHFA HPI coverage '{status}' for CBSAs: {bad}")
    m.write("fhfa_coverage", coverage, "json")
    m.close()
