"""Offer rows ("articles") as shown on product, card and seller pages."""
from __future__ import annotations

import re
from typing import List, Optional

from bs4 import BeautifulSoup, Tag

from .common import absolute, parse_int, parse_price, soup, svg_title, text, tooltip_img

CONDITIONS = {"MT": "Mint", "NM": "Near Mint", "EX": "Excellent", "GD": "Good", "LP": "Light Played", "PL": "Played", "PO": "Poor"}

# Title of an attribute icon -> flag name in the output.
FLAGS = {
    "foil": "is_foil",
    "signed": "is_signed",
    "altered": "is_altered",
    "playset": "is_playset",
    "first edition": "is_first_edition",
    "reverse holo": "is_reverse_holo",
}


def _seller(row: Tag) -> Optional[dict]:
    col = row.select_one(".col-seller")
    link = col.select_one('a[href*="/Users/"]') if col else None
    if not link:
        return None  # seller pages list their own stock: the column holds the product instead
    info = {"name": text(link), "url": absolute(link["href"]), "type": None, "country": None, "sales": None, "available_items": None}
    for el in col.select("[title]"):
        title = el["title"]
        if title.startswith("Item location:"):
            info["country"] = title.split(":", 1)[1].strip()
        elif "Sales" in title and "Available" in title:
            m = re.search(r"([\d.,]+)\s*Sales.*?([\d.,]+)\s*Available", title.replace("\xa0", " "))
            if m:
                info["sales"], info["available_items"] = parse_int(m.group(1)), parse_int(m.group(2))
    for cls, name in (("fonticon-users-powerseller", "Powerseller"), ("fonticon-users-professional", "Professional")):
        if col.select_one("." + cls):
            info["type"] = name
            break
    else:
        info["type"] = "Private"
    return info


def _product(row: Tag) -> Optional[dict]:
    """Which product the offer is for. Seller pages link the product; card pages
    (all versions) only show the expansion and rarity of each offer."""
    attrs = row.select_one(".product-attributes")
    exp = attrs.select_one(".expansion-symbol[title]") if attrs else None
    link = row.select_one('.col-seller a[href*="/Products/"]')
    if not link and not exp:
        return None
    return {
        "name": text(link) if link else None,
        "url": absolute(link["href"]) if link else None,
        "expansion": exp["title"] if exp else None,
        "expansion_url": absolute(exp.get("href")) if exp is not None and exp.get("href") else None,
        "rarity": svg_title(attrs),
        "image": tooltip_img(row.select_one(".thumbnail-icon")),
    }


def parse_offer_row(row: Tag) -> dict:
    row_id = row.get("id", "")
    offer = {
        "id": parse_int(row_id),
        "seller": _seller(row),
        "product": None,
        "condition": None,
        "condition_code": None,
        "language": None,
        "is_foil": False,
        "is_signed": False,
        "is_altered": False,
        "is_playset": False,
        "is_first_edition": False,
        "is_reverse_holo": False,
        "comments": None,
        "scan_image": None,
        "price": None,
        "price_original": None,
        "currency": "EUR",
        "quantity": None,
    }
    offer["product"] = _product(row)

    attrs = row.select_one(".product-attributes")
    if attrs:
        cond = attrs.select_one(".article-condition")
        if cond:
            offer["condition_code"] = text(cond) or None
            offer["condition"] = cond.get("title") or CONDITIONS.get(offer["condition_code"])
        for el in attrs.select("[title]"):
            if el is cond or "expansion-symbol" in el.get("class", []):
                continue
            title = el["title"]
            if "<img" in title:
                m = re.search(r'src="([^"]+)"', title)
                src = m.group(1) if m else ""
                offer["scan_image"] = absolute(src, keep_query=True) if src.startswith(("http", "//")) else None
                continue
            flag = FLAGS.get(title.strip().lower())
            if flag:
                offer[flag] = True
            elif el.get("onmouseover", "").startswith("showMsgBox") and offer["language"] is None:
                offer["language"] = title

    comment = row.select_one(".product-comments .text-truncate")
    if comment:
        offer["comments"] = text(comment) or None

    price_box = row.select_one(".col-offer .price-container") or row.select_one(".price-container")
    if price_box:
        prices = [parse_price(text(s)) for s in price_box.select("span.color-primary, span.text-nowrap")]
        prices = [p for p in prices if p is not None]
        if prices:
            offer["price"] = prices[0]
        struck = price_box.select_one("del, s, .text-decoration-line-through")
        if struck:
            offer["price_original"] = parse_price(text(struck))
    count = row.select_one(".col-offer .item-count") or row.select_one(".item-count")
    if count:
        offer["quantity"] = parse_int(text(count))
    return offer


def parse_offers(html_or_doc) -> List[dict]:
    doc = html_or_doc if isinstance(html_or_doc, BeautifulSoup) else soup(html_or_doc)
    rows = doc.select('div.article-row[id^="articleRow"], div.article-row[id^="stockRow"]')
    return [parse_offer_row(r) for r in rows]
