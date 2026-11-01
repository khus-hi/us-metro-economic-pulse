"""Checks on the latest real raw run of each source: row counts and date coverage.

Each test is skipped until that source has been pulled, so `pytest` is safe
to run on a fresh clone. After `python -m ingest run all`, these catch the
problems that matter: a metro silently missing, a series that stopped
updating, or a response that came back empty.
"""
from __future__ import annotations

import datetime as dt
import json

import pandas as pd
import pytest

from ingest import census_acs, fred, metros as xw, oews
from ingest.landing import latest_run

TODAY = dt.date.today()


def _run(source):
    run = latest_run(source)
    if run is None:
        pytest.skip(f"no raw {source} data yet")
    return run


def _metros():
    if not xw.METROS_FILE.exists():
        pytest.skip("crosswalk not built yet")
    return xw.load()


def _months_ago(year: int, month: int) -> int:
    return (TODAY.year - year) * 12 + TODAY.month - month


# ---------- crosswalk ----------
def test_crosswalk_has_50_unique_metros_with_counties():
    m = _metros()
    assert len(m) == 50
    assert m["cbsa_code"].is_unique and m["cbsa_code"].str.fullmatch(r"\d{5}").all()
    assert list(m["pop_rank"]) == list(range(1, 51))
    counties = xw.load_counties()
    assert set(counties["cbsa_code"]) == set(m["cbsa_code"])


# ---------- BLS ----------
def _bls_series(program):
    run = _run("bls")
    series = {}
    for f in run.glob(f"{program}_*.json"):
        for s in json.loads(f.read_text()).get("Results", {}).get("series", []):
            series.setdefault(s["seriesID"], []).extend(s.get("data", []))
    if not series:
        pytest.skip(f"no BLS {program} files")
    return series


def test_laus_covers_all_metros_and_recent_months():
    s = _bls_series("laus")
    metros = _metros()
    rate_ids = [k for k in s if k.endswith("03")]
    assert len(rate_ids) == len(metros), "one unemployment-rate series per metro"
    for sid, data in s.items():
        monthly = [d for d in data if d["period"] != "M13"]
        assert monthly, f"{sid} returned no data"
        latest = max((int(d["year"]), int(d["period"][1:])) for d in monthly)
        assert _months_ago(*latest) <= 4, f"{sid} is stale: latest {latest}"


def test_ces_has_total_nonfarm_for_every_metro():
    s = _bls_series("ces")
    metros = set(_metros()["cbsa_code"])
    with_total = {sid[5:10] for sid, data in s.items()
                  if sid[10:18] == "00000000" and sid.endswith("01") and data}
    assert with_total == metros


def test_jolts_and_cpi_have_recent_data():
    # State JOLTS moved to an ANNUAL release in 2026 (July 2026 release covered
    # Jul-Dec 2025), so state data can legitimately be up to ~19 months old.
    # Bimonthly metro CPI can lag 3 months.
    for program, max_lag in (("jolts", 19), ("cpi", 4)):
        for sid, data in _bls_series(program).items():
            monthly = [d for d in data if d["period"].startswith("M") and d["period"] != "M13"]
            assert monthly, f"{sid} returned no data"
            latest = max((int(d["year"]), int(d["period"][1:])) for d in monthly)
            assert _months_ago(*latest) <= max_lag, f"{sid} is stale: latest {latest}"


# ---------- FRED ----------
def test_fred_national_series_present_and_recent():
    run = _run("fred")
    for sid in fred.NATIONAL:
        body = json.loads((run / f"{sid}.json").read_text())
        obs = body["observations"]
        assert len(obs) == int(body["count"]), f"{sid}: pagination dropped rows"
        latest = dt.date.fromisoformat(obs[-1]["date"])
        assert (TODAY - latest).days < 200, f"{sid} latest {latest}"


# ---------- ACS ----------
def test_acs_has_every_top50_metro_and_all_columns():
    run = _run("census_acs")
    metros = set(_metros()["cbsa_code"])
    cols, geos = set(), None
    for f in run.glob("acs5_*.json"):
        rows = json.loads(f.read_text())
        header = rows[0]
        cols |= set(header)
        geo_idx = header.index("metropolitan statistical area/micropolitan statistical area")
        part = {r[geo_idx] for r in rows[1:]}
        geos = part if geos is None else geos & part
    assert set(census_acs.requested_columns()) <= cols
    assert metros <= geos


# ---------- BEA ----------
def test_bea_counties_cover_metros_and_recent_years():
    run = _run("bea")
    counties = set(xw.load_counties()["county_fips"])
    for f in run.glob("*.json"):
        if f.name.startswith("_"):
            continue
        data = json.loads(f.read_text())["BEAAPI"]["Results"]["Data"]
        geos = {d["GeoFips"] for d in data}
        coverage = len(counties & geos) / len(counties)
        assert coverage >= 0.95, f"{f.name}: only {coverage:.0%} of metro counties"
        assert max(int(d["TimePeriod"]) for d in data) >= TODAY.year - 2, f"{f.name} has no recent year"


# ---------- OEWS ----------
def test_oews_rows_for_every_metro():
    run = _run("oews")
    df = pd.read_csv(run / "msa_analyst_occupations.csv", dtype=str)
    metros = set(_metros()["cbsa_code"])
    assert set(df["AREA"].str.zfill(5)) == metros
    totals = df[df["OCC_CODE"] == "00-0000"]
    assert len(totals) == len(metros), "one all-occupations row per metro"
    assert set(df["OCC_CODE"]) <= oews.KEEP_OCC


# ---------- postings ----------
def test_postings_have_jobs_with_title_and_location():
    run = _run("postings")
    files = [f for f in run.glob("*.json") if not f.name.startswith("_")]
    assert files, "no boards fetched"
    total = 0
    for f in files:
        body = json.loads(f.read_text())
        for j in body["jobs"]:
            assert j.get("title") or j.get("text")
            assert j.get("location") or (j.get("categories") or {}).get("location") is not None
        total += len(body["jobs"])
    assert total > 0
