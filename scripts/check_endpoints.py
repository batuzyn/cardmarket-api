"""Live check of every flow, for every game (or the ones given).

    SCRAPEDO_TOKEN=... python scripts/check_endpoints.py [Magic Pokemon ...]

For each game it chains the flows the way a user would: expansions, top cards and
a list page; a search for a listed product; a product page with all offers; the
card across all versions and its versions page; a seller from those offers and
the seller's stock. Each step reports how many items came back and which fields
were empty. Costs about 10-15 requests (x10 credits) per game.
"""
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from cardmarket_scrapedo import Cardmarket

cm = Cardmarket()

# Fields that may legitimately be empty (depend on game / product type).
OPTIONAL = {
    "rules_text", "rarity", "number", "expansion", "expansion_url", "versions_url", "all_offers_url",
    "available_foils", "from_price_foil", "comments", "scan_image", "price_original", "product",
    "id", "image", "release_date", "product_count", "year", "language", "condition", "condition_code",
    "shipping_days", "rating", "member_since", "category", "from_price", "price_trend", "avg_1d", "avg_7d",
    "avg_30d", "available_items", "seller", "label", "number",
}


def empty_fields(items, keys=None):
    """Share of items where each required field is empty."""
    items = [i for i in items if isinstance(i, dict)]
    if not items:
        return {}
    keys = keys or [k for k in items[0] if k not in OPTIONAL]
    out = {}
    for k in keys:
        n = sum(1 for i in items if i.get(k) in (None, "", [], {}))
        if n:
            out[k] = f"{n}/{len(items)}"
    return out


def step(report, name, fn):
    t = time.time()
    try:
        value = fn()
        report[name] = {"ok": True, "s": round(time.time() - t, 1), **value}
        return value
    except Exception as e:
        report[name] = {"ok": False, "s": round(time.time() - t, 1), "error": f"{type(e).__name__}: {str(e)[:200]}"}
        return None


def check_game(game):
    r = {"game": game}
    exps = step(r, "expansions", lambda: {"n": len(x := cm.expansions(game)), "empty": empty_fields(x, ["name", "url", "slug"]), "_items": x})
    step(r, "expansion", lambda: (lambda e: {"id": e["id"], "categories": len(e["categories"])})(
        cm.expansion(game, next(e["slug"] for e in exps["_items"] if e.get("product_count")))))
    top = step(r, "top_cards", lambda: {"n": len(x := cm.top_cards(game)), "empty": empty_fields(x, ["name", "url", "from_price"]), "_items": x})
    lst = step(r, "list", lambda: {"n": len(x := list(cm.products(game, max_pages=1))), "empty": empty_fields(x, ["id", "name", "url", "from_price", "rarity"]), "_items": x})
    if lst and lst["_items"]:
        q = lst["_items"][0]["name"].split(" (")[0]
        step(r, "search", lambda: {"query": q, "n": len(x := list(cm.search(game, q, max_pages=1))), "hit": any(q.lower() in i["name"].lower() for i in x)})

    # a single from top cards (or the list), so the product has offers
    singles = [i["url"] for i in (top or {}).get("_items", []) if "/Singles/" in i["url"]] or [i["url"] for i in (lst or {}).get("_items", [])]
    prod = None
    if singles:
        prod = step(r, "product", lambda: (lambda p: {
            "url": urlsplit(p["url"] or "").path, "offers": len(p["offers"]), "complete": p["offers_complete"],
            "dupes": len(p["offers"]) - len({o["id"] for o in p["offers"]}), "history": len(p["price_history"]),
            "empty": empty_fields([p], ["id", "name", "url", "game", "category", "from_price", "available_items"]),
            "offer_empty": empty_fields(p["offers"], ["id", "seller", "price", "quantity", "condition_code", "language"]),
            "extras": sorted(p["filters"].get("extra", {})), "_p": p})(cm.product(singles[0], offers="all")))
    if prod and prod["_p"]["all_offers_url"]:
        slug = prod["_p"]["all_offers_url"].rstrip("/").rsplit("/", 1)[1]
        step(r, "card", lambda: (lambda c: {"offers": len(c["offers"]), "versions": c["version_count"],
                                            "empty": empty_fields(c["offers"], ["id", "seller", "price", "product"])})(
            cm.card(game, slug, offers=100)))
        step(r, "versions", lambda: (lambda v: {"n": len(v["versions"]), "empty": empty_fields(v["versions"], ["url", "expansion"])})(
            cm.versions(game, slug)))
    if prod and prod["_p"]["offers"]:
        # busiest seller in the offers, so the stock pages are not empty
        s = max((o["seller"] for o in prod["_p"]["offers"] if o["seller"]), key=lambda s: s["available_items"] or 0)
        step(r, "seller", lambda: (lambda x: {"name": x["name"], "type": x["type"], "categories": len(x["offer_categories"]),
                                              "evals": len(x["recent_evaluations"]),
                                              "empty": empty_fields([x], ["name", "url", "type", "country", "stats"])})(
            cm.seller(game, s["name"])))
        step(r, "seller_offers", lambda: {"n": len(x := list(cm.seller_offers(game, s["name"], max_pages=2))),
                                          "empty": empty_fields(x, ["id", "product", "price", "quantity"])})
    for v in r.values():
        if isinstance(v, dict):
            v.pop("_items", None)
            v.pop("_p", None)
    return r


if __name__ == "__main__":
    games = sys.argv[1:] or [g["id"] for g in cm.games()]
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda g: (lambda: check_game(g))() if True else None, games))
    failures = 0
    for r in results:
        bad = {k: v for k, v in r.items() if isinstance(v, dict) and (not v["ok"] or v.get("empty") or v.get("offer_empty") or v.get("dupes"))}
        failures += sum(1 for v in r.values() if isinstance(v, dict) and not v["ok"])
        print(json.dumps(r, ensure_ascii=False))
    print(f"# {len(games)} games, {failures} failed steps, {cm.http.requests_made} requests, {cm.credits_used} credits", file=sys.stderr)
    sys.exit(1 if failures else 0)
