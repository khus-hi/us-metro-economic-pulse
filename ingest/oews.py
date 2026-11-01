"""BLS OEWS May 2025, metropolitan-area file.

OEWS is a once-a-year snapshot of employment and wages by occupation. It is
published as a zipped Excel file, not via the BLS API, so we download the zip,
land it untouched, and also land a CSV of just the rows we use: our 50 CBSAs
and the analyst occupations (2018 SOC codes).
"""
from __future__ import annotations

import io
import zipfile

import pandas as pd

from .http import Client
from .landing import Manifest
from . import metros as metro_xwalk

ZIP_URL = "https://www.bls.gov/oes/special-requests/oesm25ma.zip"
AREA_DEFS_URL = "https://www.bls.gov/oes/area_definitions_m2025.xlsx"

ANALYST_SOC = {
    "15-2051": "Data Scientists",
    "15-2041": "Statisticians",
    "15-2031": "Operations Research Analysts",
    "15-1211": "Computer Systems Analysts",
    "13-1111": "Management Analysts",
    "13-1161": "Market Research Analysts and Marketing Specialists",
    "13-2051": "Financial and Investment Analysts",
    "13-1081": "Logisticians",
    "29-9021": "Health Information Technologists and Medical Registrars",
}
KEEP_OCC = set(ANALYST_SOC) | {"00-0000"}  # 00-0000 = all occupations, for context


def extract_rows(zip_bytes: bytes, cbsas: set[str]) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        xlsx = [n for n in z.namelist() if n.lower().endswith(".xlsx") and "msa" in n.lower()]
        if not xlsx:
            raise ValueError(f"No MSA xlsx in zip: {z.namelist()}")
        df = pd.read_excel(z.open(xlsx[0]), dtype=str)
    df.columns = [c.strip().upper() for c in df.columns]
    df["AREA"] = df["AREA"].str.strip().str.zfill(5)
    return df[df["AREA"].isin(cbsas) & df["OCC_CODE"].isin(KEEP_OCC)]


def run(client: Client, run_date: str) -> None:
    metros = metro_xwalk.load()
    m = Manifest("oews", run_date)
    zip_bytes = client.get(ZIP_URL).content
    m.write("oesm25ma", zip_bytes, "zip", url=ZIP_URL)
    m.write("area_definitions_m2025", client.get(AREA_DEFS_URL).content, "xlsx", url=AREA_DEFS_URL)
    rows = extract_rows(zip_bytes, set(metros["cbsa_code"]))
    missing = set(metros["cbsa_code"]) - set(rows["AREA"])
    if missing:
        m.warn(f"OEWS: no rows for CBSAs {sorted(missing)}")
    m.write("msa_analyst_occupations", rows.to_csv(index=False), "csv", url=ZIP_URL, rows=len(rows))
    m.close()
