"""Client flows with a fake transport (no network)."""
import base64
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from cardmarket_scrapedo import Cardmarket, ScrapeDoError

FIX = Path(__file__).parent / "fixtures"
PRODUCT_HTML = (FIX / "magic_product.html").read_text(encoding="utf-8")
LOAD_MORE_XML = (FIX / "magic_product_load_more.xml").read_text(encoding="utf-8")


def ajax(next_page, last):
    rows = re.search(r"<rows>(.*?)</rows>", LOAD_MORE_XML, re.S).group(1)
    return (f"<ajaxResponse><rows>{rows}</rows><newPage>{next_page}</newPage>"
            f"<maxPaginatedResultsReached>{int(last)}</maxPaginatedResultsReached></ajaxResponse>")


class FakeHttp:
    def __init__(self, posts):
        self.posts = list(posts)   # answers to the load-more POSTs, in order
        self.calls = []
        self.credits_used = 0
        self.requests_made = 0

    def get(self, url, session_id=None):
        self.calls.append(("GET", url, session_id, None))
        return PRODUCT_HTML

    def post_form(self, url, form, session_id):
        self.calls.append(("POST", url, session_id, dict(form)))
        answer = self.posts.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def test_all_offers_same_session_until_last_page():
    http = FakeHttp([ajax(2, False), ajax(3, False), ajax(-1, False)])
    p = Cardmarket(transport=http).product("https://www.cardmarket.com/en/Magic/Products/Singles/Modern-Masters-2015/Combust", offers="all")
    assert len(p["offers"]) == 50 + 3 * 50 and p["offers_complete"]
    sessions = {c[2] for c in http.calls}
    assert len(sessions) == 1 and len(next(iter(sessions))) == 7
    posts = [c for c in http.calls if c[0] == "POST"]
    assert posts[0][1] == "https://www.cardmarket.com/en/Magic/AjaxAction/Product_LoadMoreArticles"
    assert [c[3]["page"] for c in posts] == ["1", "2", "3"]
    assert posts[0][3]["idProduct"] == "282949"


def test_first_page_only_makes_one_request():
    http = FakeHttp([])
    p = Cardmarket(transport=http).product("/Magic/Products/Singles/Modern-Masters-2015/Combust")
    assert len(http.calls) == 1 and len(p["offers"]) == 50 and not p["offers_complete"]


def test_offer_limit_stops_early():
    http = FakeHttp([ajax(2, False), ajax(3, False)])
    p = Cardmarket(transport=http).product("/Magic/Products/Singles/Modern-Masters-2015/Combust", offers=80)
    assert len(p["offers"]) == 80 and len([c for c in http.calls if c[0] == "POST"]) == 1


def test_expired_form_reloads_page_with_new_session():
    import base64 as b
    expired = "<ajaxResponse><systemMessage>" + b.b64encode(b"The form has expired").decode() + "</systemMessage></ajaxResponse>"
    http = FakeHttp([expired, ajax(-1, False)])
    p = Cardmarket(transport=http).product("/Magic/Products/Singles/Modern-Masters-2015/Combust", offers="all")
    gets = [c for c in http.calls if c[0] == "GET"]
    assert len(gets) == 2 and gets[0][2] != gets[1][2]
    assert len(p["offers"]) == 100


def test_gives_up_after_flow_retries():
    err = ScrapeDoError(502, "rotation failed", "x")
    http = FakeHttp([err, err, err])
    with pytest.raises(ScrapeDoError):
        Cardmarket(transport=http, flow_retries=2).product("/Magic/Products/Singles/Modern-Masters-2015/Combust", offers="all")


def test_filters_go_into_the_page_url():
    http = FakeHttp([])
    Cardmarket(transport=http).product("/Magic/Products/Singles/X/Y", filters={"language": "1,3", "isFoil": "Y"})
    q = parse_qs(urlsplit(http.calls[0][1]).query)
    assert q == {"language": ["1,3"], "isFoil": ["Y"]}


class ListHttp:
    """Serves product lists for one expansion of 1500 products (ids 0..1499, named C0000..C1499).
    The expansion query is capped at 1000, rarity 1 has ids 0..1199 (capped too), rarity 2
    has 1200..1209, and ids 1210..1499 have no rarity at all."""

    def __init__(self):
        self.credits_used = self.requests_made = 0
        self.urls = []

    def row(self, i):
        return (f'<div id="productRow{i}" class="row"><div data-testid="name"><a href="/en/Magic/Products/Singles/S/C{i}">C{i:04d}</a></div>'
                f'<div data-testid="from_price"><span>1,00 €</span></div></div>')

    def page(self, ids, hits, page):
        ids = list(ids)
        pages = max(1, min(10, -(-min(hits, 1000) // 100)))
        return ("<html><body><form id=\"SearchResultForm\"><select name=\"idExpansion\"><option value=\"7\">Set</option></select>"
                "<select name=\"idRarity\"><option value=\"1\">Rare</option><option value=\"2\">Common</option></select></form>"
                f"<div>{min(hits, 1000)} Hits</div><div id=\"pagination\"><span class=\"mx-1\">Page {page} of {pages}</span></div>"
                + "".join(self.row(i) for i in ids[(page - 1) * 100: page * 100]) + "</body></html>")

    def get(self, url, session_id=None):
        self.urls.append(url)
        q = {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}
        page = int(q.get("site", 1))
        pool = {"1": list(range(0, 1200)), "2": list(range(1200, 1210))}.get(q.get("idRarity"), list(range(1500)))
        sort = q.get("sortBy", "popularity_desc")
        if sort == "name_desc":
            pool = pool[::-1]
        elif sort != "name_asc":
            pool = pool[len(pool) // 3:] + pool[: len(pool) // 3]   # popularity: an arbitrary order
        return self.page(pool[:1000], len(pool), page)


def test_catalog_reads_capped_expansion_completely():
    http = ListHttp()
    cm = Cardmarket(transport=http)
    rows = list(cm.catalog("Magic", workers=1))
    ids = {int(r["url"].rsplit("C", 1)[1]) for r in rows}
    assert len(rows) == len(ids)                 # de-duplicated
    assert ids == set(range(1500))               # includes products without a rarity
    assert cm.catalog_errors == []
    assert any("sortBy=name_desc" in u for u in http.urls) and any("sortBy=name_asc" in u for u in http.urls)


def test_catalog_skips_a_failing_expansion():
    class Boom(ListHttp):
        def get(self, url, session_id=None):
            if "idExpansion=7" in url:
                raise ScrapeDoError(502, "rotation failed", url)
            return super().get(url, session_id)
    cm = Cardmarket(transport=Boom())
    assert list(cm.catalog("Magic", workers=1)) == []
    assert cm.catalog_errors and cm.catalog_errors[0]["expansion_id"] == 7


def test_search_single_match_redirects_to_product():
    http = FakeHttp([])  # serves the product page, like a search that redirected
    rows = list(Cardmarket(transport=http).search("Magic", "Combust"))
    assert len(rows) == 1 and rows[0]["name"] == "Combust" and rows[0]["id"] == 282949
    assert rows[0]["url"].endswith("/Modern-Masters-2015/Combust")


def test_search_zero_results_yields_nothing():
    class Empty(FakeHttp):
        def get(self, url, session_id=None):
            return "<html><head><link rel='canonical' href='https://www.cardmarket.com/en/Magic/Products/Search'></head><body>0 Hits</body></html>"
    assert list(Cardmarket(transport=Empty([])).search("Magic", "zzzz")) == []


def test_capped_offers_are_not_complete():
    http = FakeHttp([ajax(2, False), ajax(6, True)])
    p = Cardmarket(transport=http).product("/Magic/Products/Singles/X/Y", offers="all")
    assert len(p["offers"]) == 150 and not p["offers_complete"]


def test_offer_limit_below_first_page_is_not_complete():
    http = FakeHttp([])
    p = Cardmarket(transport=http).product("/Magic/Products/Singles/X/Y", offers=10)
    assert len(p["offers"]) == 10 and not p["offers_complete"] and len(http.calls) == 1


def test_offer_limit_above_total_is_complete():
    http = FakeHttp([ajax(-1, False)])
    p = Cardmarket(transport=http).product("/Magic/Products/Singles/X/Y", offers=500)
    assert len(p["offers"]) == 100 and p["offers_complete"]


def test_zero_is_a_real_filter_value():
    url = Cardmarket(transport=FakeHttp([])).url("/Magic/Products/Singles/X/Y", sellerType=0, isFoil=None)
    assert parse_qs(urlsplit(url).query) == {"sellerType": ["0"]}


def test_only_english_site_is_supported():
    with pytest.raises(ValueError):
        Cardmarket(transport=FakeHttp([]), language="de")


def test_token_never_appears_in_errors(monkeypatch):
    import requests
    from cardmarket_scrapedo.transport import ScrapeDo

    def boom(self, method, url, **kw):
        raise requests.ConnectionError(f"Max retries exceeded with url: /?token=SECRET123&url={kw['params']['url']}")
    monkeypatch.setattr(requests.Session, "request", boom)
    cm = Cardmarket(transport=ScrapeDo(token="SECRET123", retries=0))
    out = list(cm.map(lambda u: cm.product(u), ["/Magic/Products/Singles/X/Y"]))
    assert "error" in out[0] and "SECRET123" not in out[0]["error"]
