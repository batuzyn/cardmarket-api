"""Seller (user) profile and the seller's offer list."""
from __future__ import annotations

import re

from .common import absolute, page_url, pagination, parse_int, soup, text
from .offers import parse_offers


def _evaluation_block(block) -> dict:
    """One evaluation summary: the "Very Good" share plus good/neutral/bad."""
    out = {}
    for icon in block.select("[title]"):
        pct = icon.find_next_sibling("span")
        value = parse_int(text(pct)) if pct is not None else None
        key = icon["title"].lower().replace(" ", "_")
        if key in ("very_good", "good", "neutral", "bad") and key not in out:
            out[key] = value
    return out


def parse_seller(html: str) -> dict:
    doc = soup(html)
    info = doc.select_one("#Info")
    name = text(doc.select_one("#PublicProfileHeadline")) or None
    out = {
        "name": name,
        "url": page_url(doc),
        "type": None,
        "member_since": None,
        "country": None,
        "rating": None,
        "shipping_days": None,
        "evaluations": {},
        "stats": {},
        "offer_categories": [],
        "recent_evaluations": [],
    }
    if info:
        type_icon = info.select_one('[class*="fonticon-users"][title]')
        out["type"] = type_icon["title"] if type_icon else None
        since = re.search(r"Member since (\d{4})", text(info))
        out["member_since"] = int(since.group(1)) if since else None
        rating = info.select_one('[class*="fonticon-seller-rating"][title]')
        out["rating"] = rating["title"] if rating else None
        days = re.search(r"(\d+)\s+days to you", text(info))
        out["shipping_days"] = int(days.group(1)) if days else None

    # The location icon carries the country; the text next to it is the address for shops.
    flag = doc.select_one('#PersonalInfoRow [onmouseover^="showMsgBox"][title]')
    out["country"] = flag["title"] if flag else None
    for dt in doc.select("#collapsibleAdditionalInfo dt"):
        key = text(dt).lower().replace(" ", "_")
        out["stats"][key] = parse_int(text(dt.find_next_sibling("dd")))

    summary = doc.select_one("#EvaluationElement")
    if summary:
        for label in summary.select(".personalInfo-light"):
            parent = label.find_parent("div")
            block = parent.find_parent("div") if parent is not None else None
            if block is not None:
                out["evaluations"][text(label).lower().replace(" ", "_")] = _evaluation_block(block)

    # The section is rendered twice (mobile grid and desktop slider); keep one entry per URL.
    categories = {}
    for a in doc.select('#Products a[href*="/Offers/"]'):
        url = absolute(a["href"])
        img = a.select_one("img[alt]")
        parts = [text(x) for x in a.select("h3 > span, h3 > div")]
        name = (img["alt"] if img else None) or (parts[0] if parts else None)
        count = parse_int(parts[-1]) if len(parts) > 1 else None
        entry = categories.setdefault(url, {"category": name, "count": count, "url": url})
        entry["category"] = entry["category"] or name
        entry["count"] = entry["count"] if entry["count"] is not None else count
    out["offer_categories"] = list(categories.values())

    table = doc.select_one("#EvaluationsTable")
    if table:
        for tr in table.select("tbody tr"):
            tds = tr.select("td")
            if len(tds) < 8:
                continue
            title = lambda td: td.select_one("[title]").get("title") if td.select_one("[title]") else None
            # Buyers are private people: their usernames are left out on purpose.
            out["recent_evaluations"].append({
                "buyer_country": title(tds[1]),
                "order_value": title(tds[2]),
                "date": text(tds[3]) or None,
                "description": title(tds[4]),
                "packaging": title(tds[5]),
                "comment": text(tds[6]) or None,
                "overall": title(tds[7]),
            })
    return out


def parse_seller_offers(html: str) -> dict:
    doc = soup(html)
    return {"url": page_url(doc), "offers": parse_offers(doc), **pagination(doc)}
