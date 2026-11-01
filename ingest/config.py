"""Settings and secrets.

API keys are read from a git-ignored `.env` file (see `.env.example`).
If a key is missing we fail fast with a message that says which free key
to get and where, instead of sending a request that will be rejected.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("PULSE_DATA_DIR", REPO_ROOT / "data"))
RAW_DIR = DATA_DIR / "raw"
REFERENCE_DIR = DATA_DIR / "reference"
SEEDS_DIR = REPO_ROOT / "seeds"

load_dotenv(REPO_ROOT / ".env")

KEY_SIGNUP = {
    "FRED_API_KEY": "https://fredaccount.stlouisfed.org/apikeys",
    "BLS_API_KEY": "https://data.bls.gov/registrationEngine/",
    "BEA_API_KEY": "https://apps.bea.gov/api/signup/",
    "CENSUS_API_KEY": "https://api.census.gov/data/key_signup.html",
    "CONTACT_EMAIL": "(your own email; BLS and Census file servers block anonymous scripts)",
}


class MissingKeyError(RuntimeError):
    pass


def require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingKeyError(
            f"{name} is not set. Add it to .env (free, no credit card): {KEY_SIGNUP.get(name, '')}"
        )
    return value


def user_agent() -> str:
    """BLS and Census reject requests without a descriptive User-Agent."""
    return f"us-metro-economic-pulse/0.1 (portfolio project; contact: {require('CONTACT_EMAIL')})"
