"""Export every mart table from the DuckDB warehouse to small CSV files.

Why CSV? Tableau Public and Looker Studio (both free) cannot connect to a
DuckDB file, but they can read CSVs. The marts are aggregated (about 50 metros
x months), so the files stay small enough to commit to git, which lets the
GitHub Actions run publish fresh data without any database server.

    python dashboard/export_marts.py                     # -> dashboard/data/
    python dashboard/export_marts.py --out /tmp/marts
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = os.environ.get("PULSE_WAREHOUSE", str(REPO_ROOT / "warehouse" / "pulse.duckdb"))
WARN_MB = 25  # GitHub warns at 50 MB and rejects 100 MB files; stay well below.


def export(db_path: str, out_dir: Path) -> list[tuple[str, int, float]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(db_path, read_only=True)
    tables = [r[0] for r in con.execute(
        "select table_name from information_schema.tables "
        "where table_schema = 'marts' order by table_name").fetchall()]
    if not tables:
        raise SystemExit(f"No tables in schema 'marts' of {db_path}. Run dbt first.")
    report = []
    for t in tables:
        path = out_dir / f"{t}.csv"
        # ORDER BY every column keeps row order stable, so git diffs show real changes only.
        con.execute(f"copy (select * from marts.{t} order by all) to '{path}' (header, delimiter ',')")
        rows = con.execute(f"select count(*) from marts.{t}").fetchone()[0]
        report.append((t, rows, path.stat().st_size / 1e6))
    con.close()
    return report


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--out", default=str(REPO_ROOT / "dashboard" / "data"))
    a = p.parse_args()
    too_big = False
    for table, rows, mb in export(a.db, Path(a.out)):
        flag = ""
        if mb > WARN_MB:
            flag, too_big = f"  <-- over {WARN_MB} MB, do not commit", True
        print(f"{table:<22} {rows:>8} rows  {mb:6.2f} MB{flag}")
    return 1 if too_big else 0


if __name__ == "__main__":
    sys.exit(main())
