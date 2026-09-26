"""End-to-end against the real Scrape.do API. Costs credits (~10 per request).

    SCRAPEDO_TOKEN=... RUN_LIVE=1 pytest -m live
"""
import os

import pytest

from cardmarket_scrapedo import Cardmarket

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not (os.environ.get("RUN_LIVE") and os.environ.get("SCRAPEDO_TOKEN")), reason="set RUN_LIVE=1 and SCRAPEDO_TOKEN"),
]


@pytest.fixture(scope="module")
def cm():
    return Cardmarket()


def test_product_all_offers(cm):
    p = cm.product("https://www.cardmarket.com/en/Magic/Products/Singles/Modern-Masters-2015/Combust", offers="all")
    assert p["offers_complete"] and len(p["offers"]) == 300
    assert len({o["id"] for o in p["offers"]}) == 300


def test_card_all_versions(cm):
    c = cm.card("Magic", "Ephemerate", offers=100)
    assert len(c["offers"]) == 100 and len({o["product"]["expansion"] for o in c["offers"]}) > 1


def test_list_and_search(cm):
    rows = list(cm.products("Pokemon", expansion_id=None, max_pages=1))
    assert len(rows) == 100
    assert any("Charizard" in r["name"] for r in cm.search("Pokemon", "charizard", max_pages=1))


def test_seller(cm):
    s = cm.seller("Magic", "snowc")
    assert s["name"] == "snowc" and s["offer_categories"]
