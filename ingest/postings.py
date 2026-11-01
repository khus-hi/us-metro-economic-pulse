"""Job postings from public Greenhouse and Lever job boards.

These are the same public JSON feeds that companies' own careers pages use;
no login or key. We read the company list from seeds/company_boards.csv,
fetch each board once per run, and land the JSON untouched. Classifying
titles into analyst role families and mapping locations to CBSAs happens
later in models/, so the rules are visible SQL, not hidden in a scraper.

Etiquette: one request per board per run, 1 second apart, a User-Agent with
a contact email, and only job metadata is used downstream.

Pagination: Greenhouse returns a whole board in one response. Lever pages
with `skip` and `limit`; we keep going until a page comes back short.
"""
from __future__ import annotations

import csv

import requests

from .config import SEEDS_DIR
from .http import Client
from .landing import Manifest

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER = "https://api.lever.co/v0/postings/{token}"
LEVER_PAGE = 100
SEED_FILE = SEEDS_DIR / "company_boards.csv"


def load_boards() -> list[dict[str, str]]:
    with open(SEED_FILE, newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if not r["company"].startswith("#")]


def fetch_greenhouse(client: Client, token: str) -> list[dict]:
    url = GREENHOUSE.format(token=token)
    return client.get(url, params={"content": "true"}).json().get("jobs", [])


def fetch_lever(client: Client, token: str) -> list[dict]:
    url, out, skip = LEVER.format(token=token), [], 0
    while True:
        page = client.get(url, params={"mode": "json", "skip": skip, "limit": LEVER_PAGE}).json()
        out += page
        if len(page) < LEVER_PAGE:
            return out
        skip += LEVER_PAGE


def run(client: Client, run_date: str) -> None:
    m = Manifest("postings", run_date)
    for board in load_boards():
        ats, token = board["ats"].strip().lower(), board["token"].strip()
        try:
            jobs = fetch_greenhouse(client, token) if ats == "greenhouse" else fetch_lever(client, token)
        except requests.HTTPError as e:
            m.warn(f"{ats}/{token}: HTTP {e.response.status_code} (check the board token in the seed file)")
            continue
        url = (GREENHOUSE if ats == "greenhouse" else LEVER).format(token=token)
        m.write(f"{ats}_{token}", {"company": board["company"], "ats": ats, "jobs": jobs},
                "json", url=url, rows=len(jobs))
    m.close()
