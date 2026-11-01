"""Fast tests of pure logic. No network, no data values."""
import pandas as pd
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


def test_fhfa_candidates_try_divisions_metro_and_legacy():
    counties = pd.DataFrame({
        "cbsa_code": ["14460", "14460", "17410"],
        "metro_division_code": ["14454", "15764", None],
    })
    c = fred.fhfa_candidates(counties)
    assert c["14460"] == ["ATNHPIUS14454Q", "ATNHPIUS15764Q", "ATNHPIUS14460Q"]
    assert c["17410"] == ["ATNHPIUS17410Q", "ATNHPIUS17460Q"]


def test_still_published_drops_discontinued_series(tmp_path, monkeypatch):
    import datetime as dt
    from ingest import landing
    monkeypatch.setattr(landing, "RAW_DIR", tmp_path)
    m = landing.Manifest("bls", "test")
    this_year = dt.date.today().year
    df = pd.DataFrame({"series_id": ["A", "B"], "end_year": [str(this_year), "2010"]})
    kept = bls.still_published(df, m, "CES")
    assert list(kept["series_id"]) == ["A"] and m.warnings


def test_mapping_strip_handles_padded_ids():
    import io
    raw = "series_id   \tend_year\nJTS000000390000000HIR      \t2026\n"
    df = pd.read_csv(io.StringIO(raw), sep="\t", dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df.apply(lambda s: s.str.strip())
    assert df.loc[0, "series_id"] == "JTS000000390000000HIR"


def test_summary_file_parsing_keeps_only_cbsa_rows():
    # Structure-only fixture: column names follow the Census handbook; values are placeholders.
    lines = iter([
        "GEO_ID|B19013_E001|B19013_M001",
        "0100000US|x|y",
        "310M700US14460|a|b",
    ])
    rows = census_acs.parse_summary_file(lines, ["B19013_001"])
    assert rows[0] == ["GEO_ID", "B19013_001E", "B19013_001M", census_acs.GEO_COL]
    assert rows[1:] == [["310M700US14460", "a", "b", "14460"]]


def test_sf_names():
    assert census_acs.sf_column("B15003_022", "M") == "B15003_M022"
    assert census_acs.sf_url("B19013").endswith("/5YRData/acsdt5y2024-b19013.dat")


def test_summary_file_parsing_accepts_bytes_lines():
    raw = [b"\xef\xbb\xbfGEO_ID|B19013_E001|B19013_M001", b"310M700US14460|a|b"]
    lines = (ln.decode("utf-8-sig") for ln in raw)
    rows = census_acs.parse_summary_file(lines, ["B19013_001"])
    assert rows[1][-1] == "14460"


# ---------- postings (structure-only fixtures; text is illustrative, not data) ----------
from ingest import postings  # noqa: E402
from ingest.tools_dictionary import tag_tools  # noqa: E402


@pytest.mark.parametrize("title,keep", [
    ("Senior Data Analyst", True),
    ("Product Analytics Manager", True),
    ("Business Intelligence Engineer", True),
    ("Financial Analyst, FP&A", True),
    ("Security Analyst", False),
    ("SOC Analyst II", False),
    ("Data Analyst Intern", False),
    ("Software Engineer", False),
])
def test_analyst_title_filter(title, keep):
    assert postings.is_analyst_title(title) is keep


def test_tool_tagging():
    text = "Use SQL, Python and R, build dashboards in Power BI or Tableau; dbt + Snowflake. R&D team. SaaS."
    tags = tag_tools(text)
    for t in ["SQL", "Python", "R", "Power BI", "Tableau", "dbt", "Snowflake"]:
        assert t in tags
    assert "SAS" not in tag_tools("We are a SaaS company")
    assert "R" not in tag_tools("Work with our R&D group")
    assert "Excel" in tag_tools("advanced excel skills")


def test_normalize_greenhouse_and_lever():
    gh = {"id": 1, "title": "Data Analyst", "location": {"name": "Remote - US"},
          "first_published": "2026-10-01T00:00:00-04:00", "absolute_url": "u",
          "content": "&lt;p&gt;SQL &amp;amp; Python&lt;/p&gt;"}
    r = postings.normalize_greenhouse(gh, "Co", "co")
    assert r["is_remote"] and r["posted_date"] == "2026-10-01" and r["description"] == "SQL & Python"
    lv = {"id": "a", "text": "Analyst", "categories": {"location": "Boston, MA"},
          "workplaceType": "hybrid", "createdAt": 0, "hostedUrl": "u", "descriptionPlain": "Excel"}
    r = postings.normalize_lever(lv, "Co", "co")
    assert not r["is_remote"] and r["location"] == "Boston, MA"


def test_merge_dedupes_and_tracks_first_last_seen():
    def row(i, title="Data Analyst"):
        return {"job_key": f"greenhouse:co:{i}", "ats": "greenhouse", "board": "co", "company": "Co",
                "job_id": str(i), "title": title, "location": "", "is_remote": False,
                "posted_date": "", "url": "", "tools": "", "description": ""}
    empty = pd.DataFrame(columns=postings.COLUMNS)
    day1 = postings.merge(empty, [row(1), row(2), row(2)], "2026-11-01")
    assert len(day1) == 2
    day2 = postings.merge(day1, [row(2, "Sr Data Analyst"), row(3)], "2026-11-02")
    by = day2.set_index("job_key")
    assert len(day2) == 3
    assert by.loc["greenhouse:co:1", "last_seen"] == "2026-11-01"      # closed: not seen on day 2
    assert by.loc["greenhouse:co:2", "first_seen"] == "2026-11-01"     # kept original first_seen
    assert by.loc["greenhouse:co:2", "title"] == "Sr Data Analyst"     # refreshed fields
    assert by.loc["greenhouse:co:3", "first_seen"] == "2026-11-02"
