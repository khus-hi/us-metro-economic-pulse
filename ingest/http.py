"""One HTTP client for every source.

Interview notes:
- Retries: transient failures (HTTP 429 and 5xx, dropped connections) are
  retried with exponential backoff, honouring the server's Retry-After header.
  4xx errors such as a bad series ID are NOT retried: retrying cannot fix them.
- Rate limits: each host gets a minimum gap between requests, set below each
  provider's published limit, so we never trigger a lockout (BEA locks a key
  out for an hour if you exceed its limits).
- Secrets: API keys are stripped from anything we write to disk (see redact()).
"""
from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import user_agent

log = logging.getLogger(__name__)

# Seconds between requests to the same host. Chosen conservatively:
# FRED allows 120 req/min, BEA 100 req/min, BLS/Census do not publish a per-minute cap.
MIN_INTERVAL = {
    "api.bls.gov": 1.0,
    "download.bls.gov": 1.0,
    "www.bls.gov": 1.0,
    "api.stlouisfed.org": 0.6,
    "api.census.gov": 0.5,
    "www2.census.gov": 0.5,
    "apps.bea.gov": 1.0,
    "boards-api.greenhouse.io": 1.0,
    "api.lever.co": 1.0,
}
DEFAULT_INTERVAL = 1.0

SECRET_PARAMS = {"api_key", "registrationkey", "UserID", "key"}


def redact(params: dict[str, Any] | None) -> dict[str, Any]:
    if not params:
        return {}
    return {k: ("***" if k in SECRET_PARAMS else v) for k, v in params.items()}


class Client:
    def __init__(self, total_retries: int = 5, backoff: float = 2.0, timeout: float = 60.0):
        self.timeout = timeout
        self._last_call: dict[str, float] = {}
        retry = Retry(
            total=total_retries,
            backoff_factor=backoff,  # 2s, 4s, 8s, 16s, 32s
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "POST"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session = requests.Session()
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.session.headers["User-Agent"] = user_agent()

    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        gap = MIN_INTERVAL.get(host, DEFAULT_INTERVAL)
        wait = self._last_call.get(host, 0.0) + gap - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_call[host] = time.monotonic()

    def request(self, method: str, url: str, **kwargs) -> requests.Response:
        self._throttle(url)
        kwargs.setdefault("timeout", self.timeout)
        log.info("%s %s %s", method, url, redact(kwargs.get("params")))
        resp = self.session.request(method, url, **kwargs)
        resp.raise_for_status()
        return resp

    def get(self, url: str, **kwargs) -> requests.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        return self.request("POST", url, **kwargs)
