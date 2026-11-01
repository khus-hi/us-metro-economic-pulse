"""Print a small, readable sample of each source's latest raw run.

Reads only files already on disk, so nothing here invents or fetches data.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .landing import latest_run
from .metros import METROS_FILE


def _json_files(run: Path) -> list[Path]:
    return sorted(p for p in run.glob("*.json") if not p.name.startswith("_") and p.name != "series_requested.json")


def _csv_head(path: Path, n: int = 5) -> None:
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.reader(f)):
            if i > n:
                break
            print("   ", " | ".join(row[:10]))


def show(source: str) -> None:
    print(f"\n=== {source} ===")
    run = latest_run(source)
    if run is None:
        print("    no raw data yet; run `python -m ingest run", source + "`")
        return
    man = json.loads((run / "_manifest.json").read_text()) if (run / "_manifest.json").exists() else {}
    print(f"    run: {run}  files: {len(man.get('files', []))}  warnings: {len(man.get('warnings', []))}")

    if source == "crosswalk":
        _csv_head(METROS_FILE)
        return
    if source == "oews":
        _csv_head(run / "msa_analyst_occupations.csv")
        return

    files = _json_files(run)
    if not files:
        print("    no JSON files in run")
        return
    body = json.loads(files[0].read_text())
    print(f"    file: {files[0].name}")
    if source == "bls":
        for s in body.get("Results", {}).get("series", [])[:3]:
            pts = [(d["year"], d["period"], d["value"]) for d in s.get("data", [])[:3]]
            print(f"    {s['seriesID']}: {pts}")
    elif source == "fred":
        print(f"    count={body.get('count')}", body.get("observations", [])[-3:])
    elif source == "census_acs":
        for row in body[:4]:
            print("   ", row[:6])
    elif source == "bea":
        for row in body.get("BEAAPI", {}).get("Results", {}).get("Data", [])[:4]:
            print("   ", row)
    elif source == "postings":
        for j in body.get("jobs", [])[:4]:
            loc = (j.get("location") or {}).get("name") if "location" in j else (j.get("categories") or {}).get("location")
            print(f"    {body['company']}: {j.get('title') or j.get('text')} | {loc}")
