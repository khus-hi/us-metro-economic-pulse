"""Fast tests of pure logic. No network, no data values."""
import pytest

from ingest import bls, census_acs, fred
from ingest.http import redact
from ingest.reference import DIVISION_CPI_AREA, METRO_CPI_AREA, STATES, cpi_area_for, principal_state


def test_laus_ids_follow_bls_layout():
    ids = bls.laus_ids(["MT2514460000000"])
    assert ids == [f"LAUMT25144600000000{m[-1]}" for m in bls.LAUS_MEASURES]
    assert all(len(i) == 20 for i in ids)  # LA + seasonal + 15-char area + 2-char measure


def test_cpi_ids():
    assert bls.cpi_ids(["S11A", "S11A"]) == ["CUURS11ASA0", "CUURS11ASA0L1E"]


def test_chunks_respect_api_limit():
    batches = list(bls.chunks([str(i) for i in range(120)]))
    assert [len(b) for b in batches] == [50, 50, 20]


@pytest.mark.parametrize("start,end,expected", [
    (2015, 2026, [(2015, 2026)]),
    (2000, 2026, [(2000, 2019), (2020, 2026)]),
])
def test_year_windows_max_20_years(start, end, expected):
    assert bls.year_windows(start, end) == expected


def test_principal_state_and_cpi_mapping():
    assert principal_state("Boston-Cambridge-Newton, MA-NH") == "MA"
    assert cpi_area_for("14460", "MA") == ("S11A", "metro")
    # A metro without its own CPI falls back to its Census division (Mountain for Utah).
    assert cpi_area_for("99999", "UT") == ("0480", "division")


def test_reference_tables_complete():
    assert len([s for s in STATES if s != "PR"]) == 51  # 50 states + DC
    assert set(DIVISION_CPI_AREA) == set(range(1, 10))
    assert len(METRO_CPI_AREA) == 21 and len(set(METRO_CPI_AREA.values())) == 21


def test_acs_requests_estimates_and_moes():
    cols = census_acs.requested_columns()
    assert len(cols) == 2 * len(census_acs.VARIABLES)
    assert "B19013_001E" in cols and "B19013_001M" in cols


def test_fhfa_id():
    assert fred.fhfa_id("14460") == "ATNHPIUS14460Q"


def test_secrets_redacted():
    out = redact({"api_key": "x", "UserID": "y", "registrationkey": "z", "key": "k", "series_id": "UNRATE"})
    assert out == {"api_key": "***", "UserID": "***", "registrationkey": "***", "key": "***", "series_id": "UNRATE"}
