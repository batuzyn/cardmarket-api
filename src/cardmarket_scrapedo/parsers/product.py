"""Product page: a single card or a sealed product, with its first offers."""
from __future__ import annotations

import html as htmllib
import json
import re
from typing import Dict, List, Optional

from bs4 import BeautifulSoup, Tag

from .common import absolute, game_from_path, page_url, parse_int, parse_price, soup, svg_title, text
from .offers import parse_offers

# Info-box labels -> output keys. Anything else is still kept in `attributes`.
PRICE_KEYS = {
    "From": "from_price",
    "Price Trend": "price_trend",
    "30-days average price": "avg_30d",
    "7-days average price": "avg_7d",
    "1-day average price": "avg_1d",
}


def load_more_form(doc: BeautifulSoup, action: str) -> Optional[Dict[str, str]]:
    """Hidden fields of a "Show more results" form. None when every offer is already on the page."""
    form = doc.select_one(f'form[data-ajax-action="{action}"]')
    if not form or not doc.select_one("#loadMoreButton"):
        return None
    return {i["name"]: htmllib.unescape(i.get("value", "")) for i in form.select('input[type="hidden"][name]')}


def filter_options(doc: BeautifulSoup) -> dict:
    """Which offer filters this page accepts, with their ids (they differ per game)."""
    form = doc.select_one("form.article-filter-form")
    if not form:
        return {}

    def labels(prefix: str) -> Dict[str, str]:
        out = {}
        for box in form.select(f'input[name^="{prefix}["]'):
            label = form.select_one(f'label[for="{box.get("id")}"]')
            out[box["value"]] = text(label) or box["value"]
        return out

    extras = {}
    for sel in form.select('select[name^="extra["]'):
        m = re.search(r"extra\[(\w+)\]", sel["name"])
        if m:
            extras[m.group(1)] = [o.get("value") for o in sel.select("option") if o.get("value") not in (None, "0")]
    cond = form.select_one('select[name="minCondition"]')
    return {
        "sellerCountry": labels("sellerCountry"),
        "sellerType": labels("sellerType"),
        "language": labels("language"),
        "minCondition": {o.get("value"): text(o) for o in cond.select("option") if o.get("value")} if cond else {},
        "extra": extras,  # URL params: isFoil=Y, isFirstEd=N, ...
    }


def price_history(html: str) -> List[dict]:
    """Average sell price per day from the inline chart (the longest series on the page).
    The chart has one point per day with sales, so 30 points can span several months."""
    best: List[dict] = []
    for m in re.finditer(r'"labels":(\[[^\]]*\]),"datasets":\[\{"label":"[^"]*","data":(\[[^\]]*\])', html):
        labels, values = json.loads(m.group(1)), json.loads(m.group(2))
        series = []
        for day, value in zip(labels, values):
            parts = day.split(".")
            date = f"{parts[2]}-{parts[1]}-{parts[0]}" if len(parts) == 3 else day
            series.append({"date": date, "avg_sell_price": float(value) if value is not None else None})
        if len(series) > len(best):
            best = series
    return best


def parse_product(html: str, url: Optional[str] = None) -> dict:
    doc = soup(html)
    h1 = doc.select_one(".page-title-container h1") or doc.select_one("h1")
    subtitle = h1.select_one("span") if h1 else None
    name = text(h1)
    if subtitle:
        name = name[: len(name) - len(text(subtitle))].strip()

    own_url = absolute(url) if url else page_url(doc)
    id_input = doc.select_one('form.article-filter-form input[name="idProduct"]')

    info_dl = doc.select_one("#tabContent-info dl") or doc.select_one(".info-list-container dl") or doc.select_one("dl.labeled")
    attributes: Dict[str, str] = {}
    out = {
        "id": parse_int(id_input["value"]) if id_input else None,
        "name": name or None,
        "url": own_url,
        "game": game_from_path(own_url) if own_url else None,
        "category": None,
        "expansion": None,
        "expansion_url": None,
        "rarity": None,
        "number": None,
        "image": None,
        "rules_text": None,
        "available_items": None,
        "from_price": None,
        "price_trend": None,
        "avg_30d": None,
        "avg_7d": None,
        "avg_1d": None,
        "currency": "EUR",
        "versions_url": None,
        "all_offers_url": None,
        "attributes": attributes,
        "price_history": price_history(html),
    }
    if subtitle:
        # "Modern Masters 2015 - Singles" for cards, "Booster Boxes" for sealed products
        out["category"] = text(subtitle).rsplit(" - ", 1)[-1] or None

    if info_dl:
        for dt in info_dl.select("dt"):
            dd = dt.find_next_sibling("dd")
            label, value = text(dt), text(dd)
            attributes[label] = value
            if label == "Rarity":
                out["rarity"] = svg_title(dd) or value or None
            elif label == "Number":
                out["number"] = value or None
            elif label == "Printed in":
                a = dd.select_one("a[href*='/Expansions/']")
                out["expansion"] = text(dd) or (a.get("title") if a else None)
                out["expansion_url"] = absolute(a["href"]) if a else None
            elif label == "Available items":
                out["available_items"] = parse_int(value)
            elif label in PRICE_KEYS:
                out[PRICE_KEYS[label]] = parse_price(value)
            if dd is not None:
                for a in dd.select("a[href]"):
                    if a["href"].endswith("/Versions"):
                        out["versions_url"] = absolute(a["href"])
                    elif "/Cards/" in a["href"]:
                        out["all_offers_url"] = absolute(a["href"])

    img = doc.select_one("#image img.is-front:not(.lazy)") or doc.select_one("#image img.is-front")
    if img is not None:
        out["image"] = absolute(img.get("src") or img.get("data-echo"), keep_query=True)

    rules = doc.find(lambda t: t.name in ("span", "h2", "h3") and text(t) == "Rules Text")
    if rules is not None:
        p = rules.find_next("p")
        out["rules_text"] = text(p) or None

    out["offers"] = parse_offers(doc)
    out["filters"] = filter_options(doc)
    out["load_more"] = load_more_form(doc, "Product_LoadMoreArticles")
    return out
