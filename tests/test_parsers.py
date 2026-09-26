"""Parsers against raw HTML captured through Scrape.do (tests/fixtures, see scripts/capture_fixtures.py)."""
from pathlib import Path

import pytest

from cardmarket_scrapedo.parsers import catalog, seller
from cardmarket_scrapedo.parsers.ajax import LoadMoreRefused, parse_load_more
from cardmarket_scrapedo.parsers.common import parse_int, parse_price
from cardmarket_scrapedo.parsers.offers import parse_offers
from cardmarket_scrapedo.parsers.product import parse_product

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return (FIX / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("raw,expected", [("0,02 €", 0.02), ("1.234,56 €", 1234.56), ("195,00 €", 195.0), ("N/A", None), ("", None)])
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize("raw,expected", [("3172", 3172), ("2.228", 2228), ("2000+", 2000), ("# 806", 806), ("", None)])
def test_parse_int(raw, expected):
    assert parse_int(raw) == expected


def test_product_card():
    p = parse_product(load("magic_product.html"))
    assert p["id"] == 282949 and p["name"] == "Combust" and p["game"] == "Magic"
    assert p["category"] == "Singles" and p["expansion"] == "Modern Masters 2015"
    assert p["rarity"] == "Uncommon" and p["number"] == "110"
    assert p["image"].startswith("https://product-images.s3.cardmarket.com/")
    assert p["available_items"] > 0 and p["from_price"] > 0 and p["price_trend"] is not None
    assert p["versions_url"].endswith("/Cards/Combust/Versions")
    assert "can't be countered" in p["rules_text"]
    assert len(p["price_history"]) >= 10 and p["price_history"][0]["date"][:2] == "20"
    assert len(p["offers"]) == 50
    assert p["load_more"]["idProduct"] == "282949" and p["load_more"]["__cmtkn"]
    assert p["filters"]["minCondition"]["2"] == "Near Mint"
    assert {"isFoil", "isSigned", "isAltered"} <= set(p["filters"]["extra"])


def test_product_pokemon_filters_differ():
    p = parse_product(load("pokemon_product.html"))
    assert p["url"].endswith("/Snorlax-LC64") and p["game"] == "Pokemon"
    assert p["attributes"]["Species"] == "Snorlax"
    assert {"isFirstEd", "isReverseHolo"} <= set(p["filters"]["extra"])


def test_product_sealed():
    p = parse_product(load("magic_sealed.html"))
    assert p["category"] == "Booster Boxes" and p["rarity"] is None
    assert p["from_price"] and p["avg_30d"] and len(p["offers"]) == 50


def test_offer_fields():
    offers = parse_offers(load("magic_product.html"))
    o = offers[0]
    assert o["id"] and o["seller"]["name"] and o["seller"]["url"].startswith("https://")
    assert o["seller"]["country"] and o["seller"]["type"] in ("Private", "Professional", "Powerseller")
    assert o["condition_code"] in ("MT", "NM", "EX", "GD", "LP", "PL", "PO") and o["language"]
    assert o["price"] > 0 and o["quantity"] >= 1 and o["currency"] == "EUR"
    assert any(x["comments"] for x in offers)
    assert len({x["id"] for x in offers}) == len(offers)


def test_offer_flags_ygo_first_edition():
    offers = parse_offers(load("ygo_product.html"))
    assert any(o["is_first_edition"] for o in offers)


def test_offer_scan_images_pokemon():
    offers = parse_offers(load("pokemon_product.html"))
    assert any(o["scan_image"] and o["scan_image"].startswith("https://") for o in offers)


def test_card_page_offers_carry_version():
    c = catalog.parse_card(load("magic_card.html"))
    assert c["id"] == 271470 and c["name"] == "Ephemerate" and c["version_count"] == 12
    assert c["load_more"]["idMetacard"] == "271470"
    assert all(o["product"]["expansion"] for o in c["offers"])
    assert all(o["product"]["image"] for o in c["offers"])


def test_seller_offer_rows_are_products():
    page = seller.parse_seller_offers(load("magic_user_offers.html"))
    assert len(page["offers"]) == 20 and page["pages"] and page["page"] == 1
    o = page["offers"][0]
    assert o["seller"] is None and o["product"]["url"].startswith("https://") and o["product"]["rarity"]


@pytest.mark.parametrize("name,rows", [("magic_product_load_more.xml", 50), ("magic_card_load_more.xml", 50), ("pokemon_product_load_more.xml", 29)])
def test_load_more(name, rows):
    ans = parse_load_more(load(name))
    assert len(ans["offers"]) == rows
    assert ans["last_page"] == (rows < 50)


def test_load_more_refused():
    import base64
    msg = base64.b64encode(b"<h4>The form has expired. Please try again.</h4>").decode()
    with pytest.raises(LoadMoreRefused, match="expired"):
        parse_load_more(f"<ajaxResponse><systemMessage>{msg}</systemMessage></ajaxResponse>")


def test_games():
    games = catalog.parse_games(load("magic_home.html"))
    ids = [g["id"] for g in games]
    assert {"Magic", "Pokemon", "YuGiOh", "OnePiece", "Lorcana"} <= set(ids)
    assert games[0]["name"] == "Magic: The Gathering"


def test_expansions():
    exps = catalog.parse_expansions(load("magic_expansions.html"))
    assert len(exps) > 700
    mh = next(e for e in exps if e["slug"] == "Modern-Horizons")
    assert mh["year"] == 2019 and mh["release_date"] == "14th June, 2019" and mh["product_count"] >= 337  # the list counts every product, the set page only cards


def test_expansion_page():
    e = catalog.parse_expansion(load("magic_expansion.html"))
    assert e["id"] == 2440 and e["card_count"] == 337
    assert any(c["category"] == "Booster Boxes" for c in e["categories"])


def test_product_list_view():
    page = catalog.parse_product_list(load("magic_list.html"))
    assert len(page["products"]) == 100 and page["hits"] == 337 and page["pages"] == 4
    p = page["products"][0]
    assert p["id"] and p["rarity"] and p["number"] and p["available_items"] is not None and p["from_price"]
    assert "17" in page["filters"]["idRarity"] and "1" in page["filters"]["idCategory"]


def test_product_grid_view():
    page = catalog.parse_product_list(load("magic_list_grid.html"))
    assert len(page["products"]) == 30 and page["products"][0]["from_price"]


@pytest.mark.parametrize("name", ["magic_search.html", "pokemon_list.html", "ygo_list.html"])
def test_lists_other_games(name):
    page = catalog.parse_product_list(load(name))
    assert page["products"] and all(p["url"] and p["name"] for p in page["products"])


def test_top_cards():
    top = catalog.parse_top_cards(load("magic_top_cards.html"))
    assert len(top) == 100 and top[0]["rank"] == 1 and top[0]["from_price"]


def test_versions():
    v = catalog.parse_versions(load("magic_versions.html"))
    assert v["name"] == "Ephemerate" and len(v["versions"]) == 12
    assert all(x["url"] and x["from_price"] for x in v["versions"])


def test_seller_profile():
    s = seller.parse_seller(load("magic_user.html"))
    assert s["name"] == "ilGiocoliere" and s["type"] == "Professional" and s["country"] == "Italy"
    assert s["member_since"] and s["rating"]
    assert s["stats"]["sales"] > 0 and s["evaluations"]["overall_evaluation"]["very_good"] is not None
    cats = s["offer_categories"]
    assert cats[0]["category"] == "Singles" and cats[0]["count"] > 0
    assert len({c["url"] for c in cats}) == len(cats)            # the page renders the list twice
    assert s["recent_evaluations"] and "buyer" not in s["recent_evaluations"][0]   # buyers are private people


def test_price_history_values_are_floats():
    for name in ("magic_product.html", "magic_sealed.html"):
        hist = parse_product(load(name))["price_history"]
        assert all(isinstance(p["avg_sell_price"], float) for p in hist)
