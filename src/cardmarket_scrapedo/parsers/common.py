"""Small helpers shared by all parsers."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.cardmarket.com"

_PRICE_RE = re.compile(r"(-?[\d.,]+)\s*([^\d\s.,]+)?")
_INT_RE = re.compile(r"-?\d[\d.,]*")


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def text(el: Optional[Tag]) -> str:
    if el is None:
        return ""
    return re.sub(r"\s+", " ", el.get_text(" ", strip=True).replace("\xa0", " ")).strip()


def parse_price(value: Optional[str]) -> Optional[float]:
    """'1.234,56 €' -> 1234.56 ; 'N/A' / '' -> None. Cardmarket always shows EUR."""
    if not value:
        return None
    m = _PRICE_RE.search(value.replace("\xa0", " "))
    if not m:
        return None
    num = m.group(1)
    if "," in num:  # European format: '.' thousands, ',' decimals
        num = num.replace(".", "").replace(",", ".")
    try:
        return float(num)
    except ValueError:
        return None


def parse_int(value: Optional[str]) -> Optional[int]:
    """'3172' / '2.228' / '2000+' -> int ; '' -> None."""
    if not value:
        return None
    m = _INT_RE.search(value.replace("\xa0", " "))
    if not m:
        return None
    digits = re.sub(r"[.,]", "", m.group(0))
    try:
        return int(digits)
    except ValueError:
        return None


def absolute(href: Optional[str], keep_query: bool = False) -> Optional[str]:
    """Absolute cardmarket URL. The site appends the visitor's last filter to
    navigation links, so the query is dropped unless asked for."""
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    elif href.startswith("/"):
        href = BASE_URL + href
    if not keep_query:
        parts = urlsplit(href)
        href = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    return href


def img_src(el: Optional[Tag]) -> Optional[str]:
    """Images are lazy-loaded: the real URL sits in data-echo."""
    if el is None:
        return None
    src = el.get("data-echo") or el.get("src")
    if not src or src.endswith("transparent.gif"):
        return None
    return absolute(src, keep_query=True)


def tooltip_img(el: Optional[Tag]) -> Optional[str]:
    """Thumbnails live inside a tooltip attribute as '<img src="...">'."""
    if el is None:
        return None
    raw = el.get("data-bs-title") or el.get("title") or ""
    m = re.search(r'src="([^"]+)"', raw)
    return absolute(m.group(1), keep_query=True) if m else None


def svg_title(el: Optional[Tag]) -> Optional[str]:
    """Rarity is an inline <svg title="Rare">."""
    if el is None:
        return None
    svg = el if el.name == "svg" else el.find("svg")
    if svg is None:
        return None
    return svg.get("title") or svg.get("aria-label") or svg.get("data-bs-original-title")


def game_from_path(url: str) -> Optional[str]:
    """https://www.cardmarket.com/en/Magic/... -> 'Magic'"""
    parts = urlsplit(url).path.strip("/").split("/")
    return parts[1] if len(parts) > 1 else None


def pagination(doc: BeautifulSoup) -> dict:
    """'Page 2 of 100+' and '2000+ Hits' -> numbers plus a flag when the site caps them."""
    out = {"page": None, "pages": None, "pages_capped": False, "hits": None, "hits_capped": False, "next_url": None}
    pag = doc.select_one("#pagination")
    if pag is None:  # seller offer lists use the same controls without the id
        ctrl = doc.select_one(".pagination-control")
        pag = ctrl.parent if ctrl is not None else None
    if pag:
        m = re.search(r"Page\s+(\d+)\s+of\s+(\d+)(\+?)", text(pag))
        if m:
            out.update(page=int(m.group(1)), pages=int(m.group(2)), pages_capped=bool(m.group(3)))
        nxt = pag.select_one('a[data-direction="next"][href]')
        if nxt:
            out["next_url"] = absolute(nxt["href"], keep_query=True)
    m = re.search(r"([\d.,]+)(\+?)\s+Hits", doc.get_text(" "))
    if m:
        out.update(hits=parse_int(m.group(1)), hits_capped=bool(m.group(2)))
    return out


def page_url(doc: BeautifulSoup) -> Optional[str]:
    """The page's own URL without the query: canonical link, else og:url."""
    link = doc.select_one('link[rel="canonical"][href]')
    if link:
        return absolute(link["href"])
    meta = doc.select_one('meta[property="og:url"][content]')
    return absolute(meta["content"]) if meta else None
