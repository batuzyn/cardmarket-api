"""High-level Cardmarket flows on top of Scrape.do."""
from __future__ import annotations

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, Iterable, Iterator, List, Optional, TypeVar, Union
from urllib.parse import urlencode, urlsplit

from .parsers import catalog, seller
from .parsers.ajax import LoadMoreRefused, parse_load_more
from .parsers.common import BASE_URL
from .parsers.product import parse_product
from .transport import NotFound, ScrapeDo, ScrapeDoError, new_session_id

log = logging.getLogger("cardmarket_scrapedo")

PER_PAGE = 100          # the site's maximum page size for product lists
LIST_CAP = 1000         # the site shows at most 10 pages per query
MAX_PAGES = LIST_CAP // PER_PAGE
OfferLimit = Union[int, str, None]
T = TypeVar("T")


class Cardmarket:
    """Scrape cardmarket.com through Scrape.do.

    >>> cm = Cardmarket(token="...")            # or SCRAPEDO_TOKEN env var
    >>> cm.product("https://www.cardmarket.com/en/Magic/Products/Singles/Modern-Horizons/Ephemerate", offers="all")
    """

    def __init__(self, token: Optional[str] = None, *, language: str = "en", transport: Optional[ScrapeDo] = None,
                 flow_retries: int = 3, click_delay: float = 1.0, retry_backoff: float = 3.0):
        if language != "en":
            # The parsers read English labels ("Price Trend", "Page 1 of", ...).
            raise ValueError("only the English site (language='en') is supported")
        self.http = transport or ScrapeDo(token)
        self.language = language
        self.flow_retries = flow_retries
        self.click_delay = click_delay      # seconds between "Show more results" clicks (+ up to 50% jitter)
        self.retry_backoff = retry_backoff  # wait before reloading after a failed click, grows per attempt

    # ------------------------------------------------------------------ urls
    def url(self, path_or_url: str, **params) -> str:
        """'/Magic/Expansions' or a full URL -> full URL with extra query params."""
        if path_or_url.startswith("http"):
            url = path_or_url
        else:
            path = path_or_url if path_or_url.startswith("/") else "/" + path_or_url
            if not path.startswith(f"/{self.language}/"):
                path = f"/{self.language}{path}"
            url = BASE_URL + path
        # 0 is a real filter value (sellerType=0 is "private"), so only drop None/""/False.
        params = {k: v for k, v in params.items() if v is not None and v != "" and v is not False}
        if params:
            url += ("&" if "?" in url else "?") + urlencode(params, safe=",")
        return url

    @staticmethod
    def _game_base(url: str) -> str:
        """https://www.cardmarket.com/en/Magic/... -> https://www.cardmarket.com/en/Magic"""
        parts = urlsplit(url).path.strip("/").split("/")
        return f"{BASE_URL}/{parts[0]}/{parts[1]}"

    # ------------------------------------------------------------- catalogue
    def games(self) -> List[dict]:
        return catalog.parse_games(self.http.get(self.url("/Magic")))

    def expansions(self, game: str) -> List[dict]:
        return catalog.parse_expansions(self.http.get(self.url(f"/{game}/Expansions")))

    def expansion(self, game: str, slug: str) -> dict:
        return catalog.parse_expansion(self.http.get(self.url(f"/{game}/Expansions/{slug}")))

    def top_cards(self, game: str) -> List[dict]:
        return catalog.parse_top_cards(self.http.get(self.url(f"/{game}/Data/Weekly-Top-Cards")))

    def list_page(self, url: str) -> dict:
        return catalog.parse_product_list(self.http.get(url))

    def _pages(self, first_url: str, max_pages: Optional[int] = None) -> Iterator[dict]:
        page = self.list_page(first_url)
        yield page
        last = min(page["pages"] or 1, max_pages or MAX_PAGES)
        for n in range(2, last + 1):
            yield self.list_page(self.url(first_url, site=n))

    def products(self, game: str, category: str = "Singles", *, expansion_id: Optional[int] = None,
                 rarity_id: Optional[int] = None, sort: Optional[str] = None, only_available: bool = False,
                 max_pages: Optional[int] = None) -> Iterator[dict]:
        """Rows of a product list (100 per page, at most 1000 per query)."""
        first = self.url(f"/{game}/Products/{category}", idExpansion=expansion_id, idRarity=rarity_id, sortBy=sort,
                         onlyAvailable="on" if only_available else None, mode="list", perSite=PER_PAGE)
        for page in self._pages(first, max_pages):
            yield from page["products"]

    def search(self, game: str, query: str, *, category_id: Optional[int] = None, exact: bool = False,
               only_available: bool = False, sort: Optional[str] = None, max_pages: Optional[int] = None) -> Iterator[dict]:
        first = self.url(f"/{game}/Products/Search", searchString=query, idCategory=category_id,
                         exactMatch="on" if exact else None, onlyAvailable="on" if only_available else None,
                         sortBy=sort, mode="list", perSite=PER_PAGE)
        html = self.http.get(first)
        page = catalog.parse_product_list(html)
        if not page["products"]:
            # A search with a single match redirects straight to that product's page.
            p = parse_product(html)
            if p["id"] is not None:
                yield {k: p.get(k) for k in ("id", "name", "url", "expansion", "rarity", "number", "available_items",
                                             "from_price", "image")} | {"available_foils": None, "from_price_foil": None}
            return
        yield from page["products"]
        last = min(page["pages"] or 1, max_pages or MAX_PAGES)
        for n in range(2, last + 1):
            yield from self.list_page(self.url(first, site=n))["products"]

    def catalog(self, game: str, category: str = "Singles", *, expansion_ids: Optional[Iterable[int]] = None,
                workers: int = 4) -> Iterator[dict]:
        """Every product of a category, expansion by expansion.

        A query shows at most 1000 products, so an expansion that reaches it is read
        per rarity and, to catch products without a listed rarity, by name from both
        ends. An expansion that fails is logged and skipped (see `catalog_errors`)."""
        first = self.list_page(self.url(f"/{game}/Products/{category}", mode="list", perSite=PER_PAGE))
        filters = first.get("filters", {})
        if expansion_ids is not None:
            ids = list(expansion_ids)
        else:
            ids = [int(i) for i in filters.get("idExpansion", {})]
            if not ids:
                raise RuntimeError(f"no expansion list found on {first['url']}; the page layout may have changed")
        rarities = [int(r) for r in filters.get("idRarity", {})]
        seen = set()
        self.catalog_errors = []

        def one_expansion(exp_id: int) -> List[dict]:
            try:
                return list(self._exhaust(game, category, exp_id, rarities))
            except Exception as e:  # one broken expansion must not throw away a long export
                msg = self.http.redact(f"{type(e).__name__}: {e}") if hasattr(self.http, "redact") else str(e)
                log.warning("expansion %s failed: %s", exp_id, msg)
                self.catalog_errors.append({"expansion_id": exp_id, "error": msg})
                return []

        with ThreadPoolExecutor(workers) as pool:
            for rows in pool.map(one_expansion, ids):
                for row in rows:
                    key = row.get("id") or row.get("url")
                    if key in seen:
                        continue
                    seen.add(key)
                    yield row

    def _exhaust(self, game: str, category: str, exp_id: int, rarities: List[int]) -> Iterator[dict]:
        base = dict(game=game, category=category, expansion_id=exp_id)
        head = self.list_page(self.url(f"/{game}/Products/{category}", idExpansion=exp_id, mode="list", perSite=PER_PAGE))
        if (head["hits"] or 0) < LIST_CAP:
            yield from head["products"]
            for n in range(2, (head["pages"] or 1) + 1):
                yield from self.list_page(self.url(f"/{game}/Products/{category}", idExpansion=exp_id, mode="list",
                                                   perSite=PER_PAGE, site=n))["products"]
            return
        # Products without a rarity in the dropdown never show up in a rarity query,
        # so also read the whole expansion by name from both ends.
        for rarity in [None] + rarities:
            rows = list(self._both_ends(base, rarity, exp_id))
            yield from rows

    def _both_ends(self, base: dict, rarity: Optional[int], exp_id: int) -> Iterator[dict]:
        """A capped query read A-Z and Z-A: complementary halves, so up to 2000 rows."""
        asc = list(self.products(**base, rarity_id=rarity, sort="name_asc"))
        if len(asc) < LIST_CAP:
            yield from asc
            return
        desc = list(self.products(**base, rarity_id=rarity, sort="name_desc"))
        if not {r["id"] for r in asc} & {r["id"] for r in desc}:
            log.warning("expansion %s rarity %s has more than %s products; the middle is missing",
                        exp_id, rarity, 2 * LIST_CAP)
        yield from asc
        yield from desc

    # ---------------------------------------------------------------- offers
    def _with_offers(self, url: str, parse: Callable[[str], dict], action: str, offers: OfferLimit) -> dict:
        """Load a page and, if asked, click "Show more results" on the same session.
        offers: "first" (only the page), "all", or a number of offers to stop at.

        Cardmarket answers fast repeated clicks with 429, so clicks are spaced out. A failed
        click is answered by waiting, reloading the page on a new session (the form token is
        tied to the session) and continuing from the page that failed, not from the start."""
        want = None if offers in ("all", None, "first") else int(offers)
        first_only = offers in (None, "first")
        data: Optional[dict] = None
        offers_by_id: Dict = {}
        next_page: Optional[str] = None
        last_error: Optional[Exception] = None
        for attempt in range(self.flow_retries + 1):
            if attempt:
                time.sleep(self.retry_backoff * attempt + random.uniform(0, 1))
            sid = new_session_id()
            page = parse(self.http.get(url, session_id=sid))
            form = page.pop("load_more", None)
            if data is None:
                data = page
                for o in page["offers"]:
                    offers_by_id.setdefault(o["id"], o)
            if form and next_page:
                form = dict(form, page=next_page)   # resume where the last session failed
            capped = False  # the site stopped at its offer limit, more exist
            try:
                while form and not first_only and (want is None or len(offers_by_id) < want):
                    time.sleep(self.click_delay + random.uniform(0, self.click_delay / 2))
                    answer = parse_load_more(self.http.post_form(f"{self._game_base(url)}/AjaxAction/{action}", form, sid))
                    for o in answer["offers"]:
                        offers_by_id.setdefault(o["id"], o)
                    if answer["last_page"] or not answer["next_page"]:
                        capped = answer.get("capped", False)
                        form = None
                        break
                    next_page = str(answer["next_page"])
                    form = dict(form, page=next_page)
            except (LoadMoreRefused, ScrapeDoError) as e:
                if isinstance(e, NotFound):
                    raise
                last_error = e
                log.info("load more failed (%s), reloading %s", e, url)
                continue
            result = list(offers_by_id.values())
            truncated = want is not None and len(result) > want
            data["offers"] = result[:want] if want is not None else result
            # complete: every offer the product has is in the result
            data["offers_complete"] = form is None and not capped and not truncated
            data["attempts"] = attempt + 1
            return data
        raise last_error  # type: ignore[misc]

    def product(self, url: str, *, offers: OfferLimit = "first", filters: Optional[Dict[str, str]] = None) -> dict:
        """A product page with its offers. filters are the site's URL filters,
        e.g. {"language": "1,3", "minCondition": 2, "isFoil": "Y", "sellerCountry": "7"}."""
        return self._with_offers(self.url(url, **(filters or {})), parse_product, "Product_LoadMoreArticles", offers)

    def card(self, game: str, name: str, *, offers: OfferLimit = "first", filters: Optional[Dict[str, str]] = None) -> dict:
        """All versions of a card together (/Cards/<name>), e.g. card("Magic", "Ephemerate")."""
        url = self.url(name if name.startswith("http") else f"/{game}/Cards/{name}", **(filters or {}))
        return self._with_offers(url, catalog.parse_card, "Metacard_LoadMoreArticles", offers)

    def versions(self, game: str, name: str) -> dict:
        return catalog.parse_versions(self.http.get(self.url(f"/{game}/Cards/{name}/Versions")))

    # --------------------------------------------------------------- sellers
    def seller(self, game: str, username: str) -> dict:
        return seller.parse_seller(self.http.get(self.url(f"/{game}/Users/{username}")))

    def seller_offers(self, game: str, username: str, category: str = "Singles", *,
                      filters: Optional[Dict[str, str]] = None, max_pages: Optional[int] = None) -> Iterator[dict]:
        """A seller's stock, 20 per page, at most 100 pages (2000 offers) per query.
        filters: idLanguages, idRarities, idExpansions, condition, isFoil, minPrice, maxPrice, sortBy, name ..."""
        first = self.url(f"/{game}/Users/{username}/Offers/{category}", **(filters or {}))
        page = seller.parse_seller_offers(self.http.get(first))
        yield from page["offers"]
        last = page["pages"] or 1
        if max_pages:
            last = min(last, max_pages)
        for n in range(2, last + 1):
            yield from seller.parse_seller_offers(self.http.get(self.url(first, site=n)))["offers"]

    # ------------------------------------------------------------- utilities
    def map(self, fn: Callable[[T], dict], items: Iterable[T], workers: int = 5) -> Iterator[dict]:
        """Run fn over items in parallel; failures come back as {"input": ..., "error": ...}."""
        def safe(item):
            try:
                return fn(item)
            except Exception as e:  # keep going: one bad product must not stop a batch
                msg = f"{type(e).__name__}: {e}"
                return {"input": item, "error": self.http.redact(msg) if hasattr(self.http, "redact") else msg}
        with ThreadPoolExecutor(workers) as pool:
            yield from pool.map(safe, items)

    @property
    def credits_used(self) -> int:
        return self.http.credits_used
