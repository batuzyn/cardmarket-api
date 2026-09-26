"""Scrape.do transport: every request to cardmarket goes through the Scrape.do API."""
from __future__ import annotations

import os
import secrets
import threading
import time
from typing import Dict, Optional

import requests

DEFAULT_API = "https://api.scrape.do/"


class ScrapeDoError(Exception):
    def __init__(self, status: int, message: str, url: str):
        super().__init__(f"{status} for {url}: {message[:300]}")
        self.status = status
        self.url = url


class NotFound(ScrapeDoError):
    """Cardmarket answered 404: the product, expansion or seller does not exist."""


def new_session_id() -> str:
    """Scrape.do sessionId: digits only, at most 7 characters."""
    return str(secrets.randbelow(9_000_000) + 1_000_000)


class ScrapeDo:
    """Thin, thread-safe client for the Scrape.do API.

    Cardmarket needs `super=true`. Pass the same `session_id` to requests that
    must look like one visitor (a page and its "Show more results" calls).
    """

    RETRY_STATUS = {429, 500, 502, 503, 504, 520, 522, 524}

    def __init__(self, token: Optional[str] = None, api: Optional[str] = None, timeout: float = 120,
                 retries: int = 3, backoff: float = 2.0, extra_params: Optional[Dict[str, str]] = None):
        self.token = token or os.environ.get("SCRAPEDO_TOKEN")
        if not self.token:
            raise ValueError("Scrape.do token missing: pass token=... or set SCRAPEDO_TOKEN")
        self.api = api or os.environ.get("SCRAPEDO_API", DEFAULT_API)
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.extra_params = extra_params or {}
        self._local = threading.local()
        self._lock = threading.Lock()
        self.requests_made = 0
        self.credits_used = 0

    def _http(self) -> requests.Session:
        if not hasattr(self._local, "http"):
            self._local.http = requests.Session()
        return self._local.http

    def _params(self, url: str, session_id: Optional[str]) -> dict:
        params = {"token": self.token, "url": url, "super": "true", **self.extra_params}
        if session_id:
            params["sessionId"] = session_id
        return params

    def _account(self, resp: requests.Response) -> None:
        cost = resp.headers.get("Scrape.do-Request-Cost")
        with self._lock:
            self.requests_made += 1
            if cost and cost.isdigit():
                self.credits_used += int(cost)

    def request(self, method: str, url: str, session_id: Optional[str] = None,
                form: Optional[Dict[str, str]] = None, retries: Optional[int] = None) -> str:
        attempts = (self.retries if retries is None else retries) + 1
        last: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                resp = self._http().request(
                    method, self.api, params=self._params(url, session_id), timeout=self.timeout,
                    files={k: (None, v) for k, v in form.items()} if form is not None else None,
                )
            except requests.RequestException as e:  # network trouble: retry
                # requests puts the full API URL, token included, in its message.
                last = ScrapeDoError(0, f"{type(e).__name__}: {self.redact(str(e))}", url)
            else:
                self._account(resp)
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code == 404:
                    raise NotFound(404, self.redact(resp.text), url)
                last = ScrapeDoError(resp.status_code, self.redact(resp.text), url)
                if resp.status_code not in self.RETRY_STATUS:
                    raise last
            if attempt + 1 < attempts:
                time.sleep(self.backoff * (attempt + 1))
        raise last from None  # type: ignore[misc]

    def redact(self, text: str) -> str:
        return text.replace(self.token, "***") if self.token else text

    def get(self, url: str, session_id: Optional[str] = None) -> str:
        return self.request("GET", url, session_id)

    def post_form(self, url: str, form: Dict[str, str], session_id: str) -> str:
        """multipart/form-data POST, like a browser form. Not retried: a failed
        "load more" call is recovered by reloading the page (new token)."""
        return self.request("POST", url, session_id, form=form, retries=0)
