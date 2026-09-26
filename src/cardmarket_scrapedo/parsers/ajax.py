"""Answer of the "Show more results" call (Product_/Metacard_LoadMoreArticles)."""
from __future__ import annotations

import base64
import re
from typing import Optional

from .offers import parse_offers


class LoadMoreRefused(Exception):
    """Cardmarket answered with a message instead of offers (e.g. "The form has expired")."""


def _field(xml: str, tag: str) -> Optional[str]:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    return m.group(1) if m else None


def _b64(value: Optional[str]) -> str:
    return base64.b64decode(value).decode("utf-8", "replace") if value else ""


def parse_load_more(xml: str) -> dict:
    """-> {"offers": [...], "next_page": int|None, "last_page": bool, "capped": bool}"""
    rows = _field(xml, "rows")
    if rows is None:
        message = re.sub(r"<[^>]+>", " ", _b64(_field(xml, "systemMessage")) or xml[:300])
        raise LoadMoreRefused(re.sub(r"\s+", " ", message).strip()[:200])
    next_page = int(_field(xml, "newPage") or 0)
    capped = _field(xml, "maxPaginatedResultsReached") == "1"  # the site's offer limit, more exist
    return {
        "offers": parse_offers(_b64(rows)),
        "next_page": next_page if next_page > 0 else None,
        "last_page": capped or next_page <= 0,
        "capped": capped,
    }
