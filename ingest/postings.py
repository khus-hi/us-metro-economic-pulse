"""Analyst job postings from public Greenhouse and Lever job boards.

Pipeline for each run (interview notes):
1. Read the company list from seeds/companies.csv (company, ats, token).
2. Check robots.txt for each API host once per run; skip a host if it disallows us.
3. Fetch each board (a delay between requests, set by POSTINGS_DELAY_SECONDS,
   default 2s). Greenhouse returns a whole board at once; Lever pages with
   skip/limit. Raw JSON is landed untouched in data/raw/postings/{run_date}/.
4. Normalize to one row per job: title, company, location, remote flag,
   posted date, plain-text description, and tools tagged from the keyword
   dictionary in tools_dictionary.py.
5. Keep only analyst titles (rules below, easy to read and change).
6. Dedupe across daily runs by merging into data/postings/postings.csv, keyed by
   ats + board + job id. `first_seen` and `last_seen` show how long a role
   stayed open; a job missing from today's pull keeps its old `last_seen`.
"""
from __future__ import annotations

import csv
import datetime as dt
import html
import os
import re
import time
import urllib.robotparser
from urllib.parse import urlparse

import pandas as pd
import requests

from .config import DATA_DIR, SEEDS_DIR
from .http import Client
from .landing import Manifest
from .tools_dictionary import tag_tools

GREENHOUSE = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
LEVER = "https://api.lever.co/v0/postings/{token}"
LEVER_PAGE = 100
SEED_FILE = SEEDS_DIR / "companies.csv"
MASTER_FILE = DATA_DIR / "postings" / "postings.csv"
DELAY = float(os.environ.get("POSTINGS_DELAY_SECONDS", "2"))

# --- Analyst title rules ----------------------------------------------------
INCLUDE = re.compile(
    r"\banalysts?\b|\banalytics\b|\bbusiness intelligence\b|\bBI (?:developer|engineer|analyst)\b"
    r"|\binsights?\b.*\b(?:manager|lead|associate)\b|\bdata scientists?\b",
    re.IGNORECASE)
# Analyst-titled roles outside our target tracks (security/SOC analysts etc.).
EXCLUDE = re.compile(
    r"\bsecurity\b|\bthreat\b|\bcyber\b|\bSOC\b|\bmalware\b|\bpenetration\b|\bintern(ship)?\b",
    re.IGNORECASE)

COLUMNS = ["job_key", "ats", "board", "company", "job_id", "title", "location", "is_remote",
           "posted_date", "url", "tools", "description", "first_seen", "last_seen"]


def is_analyst_title(title: str) -> bool:
    return bool(INCLUDE.search(title or "")) and not EXCLUDE.search(title or "")


def html_to_text(raw: str) -> str:
    text = html.unescape(raw or "")          # Greenhouse escapes its HTML once
    text = re.sub(r"<(br|/p|/li|/h\d)[^>]*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


REMOTE = re.compile(r"\bremote\b|\banywhere\b|\bwork from home\b|\bdistributed\b", re.IGNORECASE)


def normalize_greenhouse(job: dict, company: str, board: str) -> dict:
    location = (job.get("location") or {}).get("name", "") or ""
    offices = ", ".join(o.get("name", "") for o in job.get("offices") or [])
    posted = job.get("first_published") or job.get("updated_at") or ""
    return {
        "ats": "greenhouse", "board": board, "company": company, "job_id": str(job.get("id")),
        "title": (job.get("title") or "").strip(), "location": location.strip(),
        "is_remote": bool(REMOTE.search(location) or REMOTE.search(offices) or REMOTE.search(job.get("title") or "")),
        "posted_date": posted[:10], "url": job.get("absolute_url", ""),
        "description": html_to_text(job.get("content", "")),
    }


def normalize_lever(job: dict, company: str, board: str) -> dict:
    cats = job.get("categories") or {}
    location = cats.get("location") or ", ".join(cats.get("allLocations") or [])
    created = job.get("createdAt")
    posted = dt.datetime.fromtimestamp(created / 1000, dt.timezone.utc).date().isoformat() if created else ""
    parts = [job.get("descriptionPlain") or html_to_text(job.get("description", ""))]
    for lst in job.get("lists") or []:
        parts += [lst.get("text", ""), html_to_text(lst.get("content", ""))]
    parts.append(job.get("additionalPlain") or "")
    return {
        "ats": "lever", "board": board, "company": company, "job_id": str(job.get("id")),
        "title": (job.get("text") or "").strip(), "location": (location or "").strip(),
        "is_remote": (job.get("workplaceType") == "remote") or bool(REMOTE.search(location or "")),
        "posted_date": posted, "url": job.get("hostedUrl", ""),
        "description": "\n".join(p for p in parts if p).strip(),
    }


def to_rows(jobs: list[dict], ats: str, company: str, board: str) -> list[dict]:
    norm = normalize_greenhouse if ats == "greenhouse" else normalize_lever
    rows = []
    for job in jobs:
        r = norm(job, company, board)
        if not is_analyst_title(r["title"]):
            continue
        r["tools"] = ";".join(tag_tools(f"{r['title']}\n{r['description']}"))
        r["job_key"] = f"{ats}:{board}:{r['job_id']}"
        rows.append(r)
    return rows


def merge(master: pd.DataFrame, today_rows: list[dict], run_date: str) -> pd.DataFrame:
    """Upsert today's jobs into the master table (dedupe across daily runs)."""
    new = pd.DataFrame(today_rows, columns=[c for c in COLUMNS if c not in ("first_seen", "last_seen")])
    new = new.drop_duplicates("job_key", keep="last")
    new["last_seen"] = run_date
    first_seen = master.set_index("job_key")["first_seen"] if len(master) else pd.Series(dtype=str)
    new["first_seen"] = new["job_key"].map(first_seen).fillna(run_date)
    kept = master[~master["job_key"].isin(new["job_key"])] if len(master) else master
    out = pd.concat([kept, new[COLUMNS]], ignore_index=True)
    return out.sort_values(["company", "title", "job_key"]).reset_index(drop=True)


def load_companies() -> list[dict[str, str]]:
    if not SEED_FILE.exists():
        raise FileNotFoundError(f"Add {SEED_FILE} with columns company,ats,token")
    with open(SEED_FILE, newline="", encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r.get("company") and not r["company"].startswith("#")]
    bad = [r for r in rows if r["ats"].strip().lower() not in ("greenhouse", "lever")]
    if bad:
        raise ValueError(f"ats must be 'greenhouse' or 'lever': {bad}")
    return rows


class Robots:
    """One robots.txt check per host per run. A missing robots.txt (404) means allowed."""

    def __init__(self, client: Client, m: Manifest):
        self.client, self.m, self.cache = client, m, {}

    def allowed(self, url: str) -> bool:
        host = urlparse(url).netloc
        if host not in self.cache:
            rp = urllib.robotparser.RobotFileParser()
            try:
                rp.parse(self.client.get(f"https://{host}/robots.txt").text.splitlines())
            except requests.HTTPError as e:
                rp.parse([] if e.response.status_code in (404, 410) else ["User-agent: *", "Disallow: /"])
            self.cache[host] = rp
        ok = self.cache[host].can_fetch(self.client.session.headers["User-Agent"], url)
        if not ok:
            self.m.warn(f"robots.txt disallows {url}; skipped")
        return ok


def fetch_greenhouse(client: Client, token: str) -> list[dict]:
    return client.get(GREENHOUSE.format(token=token), params={"content": "true"}).json().get("jobs", [])


def fetch_lever(client: Client, token: str) -> list[dict]:
    url, out, skip = LEVER.format(token=token), [], 0
    while True:
        page = client.get(url, params={"mode": "json", "skip": skip, "limit": LEVER_PAGE}).json()
        out += page
        if len(page) < LEVER_PAGE:
            return out
        skip += LEVER_PAGE
        time.sleep(DELAY)


def run(client: Client, run_date: str) -> None:
    m = Manifest("postings", run_date)
    robots = Robots(client, m)
    rows = []
    for co in load_companies():
        ats, token, company = co["ats"].strip().lower(), co["token"].strip(), co["company"].strip()
        url = (GREENHOUSE if ats == "greenhouse" else LEVER).format(token=token)
        if not robots.allowed(url):
            continue
        try:
            jobs = fetch_greenhouse(client, token) if ats == "greenhouse" else fetch_lever(client, token)
        except requests.HTTPError as e:
            m.warn(f"{ats}/{token}: HTTP {e.response.status_code} (check the token in companies.csv)")
            continue
        finally:
            time.sleep(DELAY)
        m.write(f"{ats}_{token}", {"company": company, "ats": ats, "jobs": jobs}, "json", url=url, rows=len(jobs))
        kept = to_rows(jobs, ats, company, token)
        if jobs and not kept:
            m.warn(f"{company}: {len(jobs)} jobs, none with analyst titles")
        rows += kept

    MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    master = pd.read_csv(MASTER_FILE, dtype=str, keep_default_na=False) if MASTER_FILE.exists() \
        else pd.DataFrame(columns=COLUMNS)
    merged = merge(master, rows, run_date)
    merged.to_csv(MASTER_FILE, index=False)
    m.files.append({"file": str(MASTER_FILE), "rows": len(merged),
                    "new_today": int((merged["first_seen"] == run_date).sum()),
                    "seen_today": int((merged["last_seen"] == run_date).sum())})
    m.close()
