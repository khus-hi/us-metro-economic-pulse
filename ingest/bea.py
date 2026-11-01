"""BEA Regional API, county level.

BEA stopped publishing metro-area GDP and personal income in Feb 2026, so we
pull the county tables and add counties up to metros in the models/ layer:
- CAGDP2 line 1: GDP, current dollars, all industries (additive across counties)
- CAINC1 lines 1-3: personal income, population, per-capita personal income
  (we sum lines 1 and 2 and recompute per-capita; never sum line 3)

Real (chained-dollar) GDP is not additive, so it is not pulled for v1.

BEA rate limits: 100 requests/minute, 30 errors/minute, 100 MB/minute;
exceeding them locks the key for an hour. The shared client spaces calls
1 second apart, and we make only a handful of calls.
"""
from __future__ import annotations

from .config import require
from .http import Client
from .landing import Manifest

URL = "https://apps.bea.gov/api/data"
TABLES = {
    "CAGDP2": ["1"],
    "CAINC1": ["1", "2", "3"],
}


def run(client: Client, run_date: str, years: str = "LAST10") -> None:
    m = Manifest("bea", run_date)
    key = require("BEA_API_KEY")
    for table, lines in TABLES.items():
        for line in lines:
            params = {"UserID": key, "method": "GetData", "datasetname": "Regional",
                      "TableName": table, "LineCode": line, "GeoFips": "COUNTY",
                      "Year": years, "ResultFormat": "JSON"}
            body = client.get(URL, params=params).json()
            results = body.get("BEAAPI", {}).get("Results", {})
            if "Error" in body.get("BEAAPI", {}) or "Error" in results:
                m.warn(f"{table} line {line}: {body['BEAAPI'].get('Error') or results.get('Error')}")
            rows = len(results.get("Data", []))
            m.write(f"{table}_line{line}", body, "json", url=URL,
                    params={k: v for k, v in params.items() if k != "UserID"}, rows=rows)
    m.close()
