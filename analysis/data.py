"""Load the marts. Default source is the committed CSVs in dashboard/data/, so
anyone can reproduce the analysis from a fresh clone without API keys or a
warehouse. Pass a DuckDB path to read the live warehouse instead."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
CSV_DIR = REPO_ROOT / "dashboard" / "data"
OUT_DIR = Path(__file__).resolve().parent / "output"

STR_COLS = {"cbsa_code": str, "soc_code": str, "principal_state_fips": str, "cpi_area_code": str}


def load(table: str, csv_dir: Path = CSV_DIR, duckdb_path: str | None = None) -> pd.DataFrame:
    if duckdb_path:
        import duckdb
        with duckdb.connect(duckdb_path, read_only=True) as con:
            df = con.execute(f"select * from marts.{table}").df()
    else:
        df = pd.read_csv(csv_dir / f"{table}.csv", dtype=STR_COLS)
    for c in ("month_date", "first_seen", "last_seen", "posted_date"):
        if c in df:
            df[c] = pd.to_datetime(df[c])
    return df
