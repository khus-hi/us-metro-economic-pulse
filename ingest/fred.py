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


def fhfa_candidates(counties) -> dict[str, list[list[str]]]:
    """For each metro, the FHFA IDs to try, in order of preference.

    FHFA publishes metros split into metropolitan divisions (New York, LA,
    Chicago, Dallas, Boston, ...) per division, and its division codes don't
    always match the 2023 OMB codes. So we try the divisions first, then the
    whole-metro code, and record which metros end up with no house price index.
    """
    out = {}
    for cbsa, grp in counties.groupby("cbsa_code"):
        divs = sorted(grp["metro_division_code"].dropna().unique())
        options = [[fhfa_id(d) for d in divs]] if divs else []
        out[cbsa] = options + [[fhfa_id(cbsa)]]
    return out


def fhfa_ids(counties) -> list[str]:
    return [i for opts in fhfa_candidates(counties).values() for i in opts[0]]


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
    coverage = {}
    for cbsa, options in fhfa_candidates(metro_xwalk.load_counties()).items():
        coverage[cbsa] = None
        for ids in options:
            got = [sid for sid in ids if _fetch(client, m, sid, start_year)]
            if got:
                coverage[cbsa] = got
                break
    missing = sorted(c for c, v in coverage.items() if v is None)
    if missing:
        m.warn(f"FHFA HPI not found on FRED for CBSAs: {missing}")
    m.write("fhfa_coverage", coverage, "json")
    m.close()
