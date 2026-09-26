"""Browsing pages: games, expansions, product lists/search, card versions, top sellers."""
from __future__ import annotations

import re
from typing import List, Optional

from .common import (BASE_URL as BASE, absolute, game_from_path, img_src, page_url, pagination, parse_int, parse_price,
                     soup, svg_title, text, tooltip_img)
from .offers import parse_offers
from .product import load_more_form

_NON_GAME = {"Login", "Signup", "Users", "AdvancedSearch", "Policies", "AboutUs"}


def parse_games(html: str) -> List[dict]:
    """Game switcher on any page: [{"id": "Magic", "name": "Magic: The Gathering", "url": ...}]"""
    doc = soup(html)
    names = {}
    for a in doc.select('a[href^="/en/"]'):
        m = re.fullmatch(r"/en/([A-Za-z]+)", a["href"])
        if not m or m.group(1) in _NON_GAME:
            continue
        label = text(a) or a.get("title") or a.get("aria-label") or ""
        if label in ("", "Back to Home"):
            label = ""
        if m.group(1) not in names or (not names[m.group(1)] and label):
            names[m.group(1)] = label
    # The current game is not in the switcher list; its name is on the dropdown button.
    current = doc.select_one(".games-dropdown .dropdown-toggle")
    first = next(iter(names), None)
    if current is not None and first and not names[first]:
        names[first] = text(current)
    return [{"id": gid, "name": name or gid, "url": f"{BASE}/en/{gid}"} for gid, name in names.items()]


def parse_expansions(html: str) -> List[dict]:
    doc = soup(html)
    out = []
    for group in doc.select("section.expansion-group") or [doc]:
        heading = group.select_one("h2")
        year = parse_int(text(heading).split(" ")[0]) if heading else None
        for row in group.select(".expansion-row[data-url]"):
            cols = row.select(":scope > div")
            count = release = None
            for col in cols:
                t = text(col)
                if re.search(r"\d+\s+(Cards|Products)$", t):
                    count = parse_int(t)
                elif re.search(r"\d{4}$", t) and not col.select_one("a"):
                    release = t
            url = absolute(row["data-url"])
            out.append({
                "name": row.get("data-local-name") or text(row.select_one("a")),
                "slug": url.rstrip("/").rsplit("/", 1)[-1],
                "url": url,
                "year": year,
                "release_date": release,
                "product_count": count,
                "image": img_src(row.select_one("img")),
            })
    return out


def parse_expansion(html: str) -> dict:
    """Expansion landing page: id, release date and the product categories it has."""
    doc = soup(html)
    exp_id = None
    categories = []
    for a in doc.select('a[href*="/Products/"]'):
        href = a["href"]
        m = re.search(r"idExpansion=(\d+)", href)
        if m:
            exp_id = exp_id or int(m.group(1))
        name = text(a.select_one("h2, h3, .card-title")) or text(a)
        price = re.search(r"From\s+([\d.,]+\s*€)", text(a))
        if "galleryBox" in a.get("class", []) or price:
            cat = re.sub(r"\s*From\s+[\d.,]+\s*€.*$", "", name).strip()
            categories.append({
                "category": cat,
                "url": absolute(href, keep_query=True),
                "from_price": parse_price(price.group(1)) if price else None,
            })
    h1 = doc.select_one("h1")
    head = text(h1.parent) if h1 else ""
    release = re.search(r"(\d{1,2}(?:st|nd|rd|th) \w+, \d{4})", head)
    count = re.search(r"(\d+)\s+Cards", head)
    return {
        "id": exp_id,
        "name": text(h1) or None,
        "url": page_url(doc),
        "release_date": release.group(1) if release else None,
        "card_count": int(count.group(1)) if count else None,
        "categories": categories,
    }


def _list_row(row) -> dict:
    """List view (mode=list): one product per row, cells tagged with data-testid."""
    cell = lambda name: row.select_one(f'[data-testid="{name}"]')
    link = cell("name").select_one("a") if cell("name") else None
    exp = cell("expansion")
    exp_a = exp.select_one("[title]") if exp else None
    return {
        "id": parse_int(row.get("id")),
        "name": text(link) or None,
        "url": absolute(link["href"]) if link else None,
        "expansion": exp_a.get("title") if exp_a else None,
        "rarity": svg_title(cell("rarity")),
        "number": text(cell("collector_number")).lstrip("# ").strip() or None,
        "available_items": parse_int(text(cell("availability"))),
        "from_price": parse_price(text(cell("from_price"))),
        "available_foils": parse_int(text(cell("available_foils"))),
        "from_price_foil": parse_price(text(cell("price_from_foils"))),
        "image": tooltip_img(row.select_one(".thumbnail-icon")),
    }


def _gallery_box(a) -> dict:
    """Grid view / top sellers: a card tile."""
    title = a.select_one(".card-title")
    exp = title.select_one("[title]") if title else None
    price = re.search(r"From\s+([\d.,]+\s*€)", text(a))
    return {
        "id": None,
        "name": text(title) or a.get("title") or None,
        "url": absolute(a["href"]),
        "expansion": exp["title"] if exp else None,
        "rarity": None,
        "number": None,
        "available_items": None,
        "from_price": parse_price(price.group(1)) if price else None,
        "available_foils": None,
        "from_price_foil": None,
        "image": img_src(a.select_one("img")),
    }


def list_filters(doc) -> dict:
    """Id tables of the list/search form: categories, expansions, rarities, sort orders."""
    form = doc.select_one("#SearchResultForm")
    if not form:
        return {}
    out = {}
    for name in ("idCategory", "idExpansion", "idRarity", "sortBy"):
        sel = form.select_one(f'select[name="{name}"]')
        if sel:
            out[name] = {o.get("value"): text(o) for o in sel.select("option") if text(o) and o.get("value") not in (None, "0")}
    return out


def parse_product_list(html: str) -> dict:
    """Category, expansion and search result pages (list or grid view)."""
    doc = soup(html)
    rows = doc.select('[id^="productRow"]')
    products = [_list_row(r) for r in rows] if rows else [_gallery_box(a) for a in doc.select("a.galleryBox[href]")]
    return {"url": page_url(doc), "products": products, **pagination(doc), "filters": list_filters(doc)}


def parse_top_cards(html: str) -> List[dict]:
    doc = soup(html)
    grid = doc.select_one("#DataGrid") or doc
    items = [_gallery_box(a) for a in grid.select("a.galleryBox[href]")]
    for rank, item in enumerate(items, 1):
        item["rank"] = rank
    return items


def parse_versions(html: str) -> dict:
    """/Cards/<name>/Versions: every printing of a card."""
    doc = soup(html)
    versions = []
    for a in doc.select("#ReprintSection a.card[href]"):
        name_el = a.select_one("h3 span.text-start") or a.select_one("h3")
        exp = a.select_one("h3 [title]")
        body = text(a.select_one(".card-body"))
        avail = re.search(r"([\d.,]+)\s+Available", body, re.I)
        price = re.search(r"From\s+([\d.,]+\s*€)", body)
        versions.append({
            "expansion": exp["title"] if exp else None,
            "label": text(name_el) or None,  # e.g. "Mystical Archive Version 2"
            "url": absolute(a["href"]),
            "available_items": parse_int(avail.group(1)) if avail else None,
            "from_price": parse_price(price.group(1)) if price else None,
            "image": img_src(a.select_one("img")),
        })
    h1 = doc.select_one("h1")
    sub = h1.select_one("span") if h1 else None
    name = text(h1)[: len(text(h1)) - len(text(sub))].strip() if sub else text(h1)
    return {"name": name or None, "url": page_url(doc), "versions": versions}


def parse_card(html: str) -> dict:
    """/Cards/<name>: offers across all versions of a card."""
    doc = soup(html)
    h1 = doc.select_one(".page-title-container h1")
    sub = h1.select_one("span") if h1 else None
    name = text(h1)[: len(text(h1)) - len(text(sub))].strip() if sub else text(h1)
    info = {}
    for dt in doc.select("dl.labeled dt"):
        info[text(dt)] = text(dt.find_next_sibling("dd"))
    id_input = doc.select_one('form[data-ajax-action="Metacard_LoadMoreArticles"] input[name="idMetacard"]')
    url = page_url(doc)
    return {
        "id": parse_int(id_input["value"]) if id_input else None,
        "name": name or None,
        "url": url,
        "game": game_from_path(url) if url else None,
        "available_items": parse_int(info.get("No. of Available Items")),
        "version_count": parse_int(info.get("No. of Versions")),
        "from_price": parse_price(info.get("Available from")),
        "price_trend": parse_price(info.get("Price Trend")),
        "currency": "EUR",
        "attributes": info,
        "offers": parse_offers(doc),
        "load_more": load_more_form(doc, "Metacard_LoadMoreArticles"),
    }
