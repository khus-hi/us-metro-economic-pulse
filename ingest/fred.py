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


def fhfa_ids(counties) -> list[str]:
    """FHFA publishes metros that are split into metropolitan divisions (New York,
    Los Angeles, Chicago, Dallas, Boston, ...) only at the division level, so for
    those metros we request every division and combine them later in models/."""
    ids = []
    for cbsa, grp in counties.groupby("cbsa_code"):
        divs = sorted(grp["metro_division_code"].dropna().unique())
        ids += [fhfa_id(d) for d in divs] if divs else [fhfa_id(cbsa)]
    return ids


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


def run(client: Client, run_date: str, start_year: int) -> None:
    m = Manifest("fred", run_date)
    series = list(NATIONAL) + fhfa_ids(metro_xwalk.load_counties())
    for sid in series:
        try:
            body = observations(client, sid, f"{start_year}-01-01")
        except requests.HTTPError as e:
            # FRED answers 400 for an ID that does not exist; record it, keep going.
            m.warn(f"{sid}: {e.response.status_code} {e.response.text[:200]}")
            continue
        m.write(sid, body, "json", url=URL, params={"series_id": sid, "observation_start": start_year},
                rows=len(body["observations"]))
    m.close()
