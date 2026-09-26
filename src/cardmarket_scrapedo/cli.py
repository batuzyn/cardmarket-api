"""Command line: `cardmarket <command> ...`  (run `cardmarket -h`)."""
from __future__ import annotations

import argparse
import json
import logging
import sys
from .client import Cardmarket


def _filters(pairs):
    out = {}
    for pair in pairs or []:
        key, _, value = pair.partition("=")
        out[key] = value
    return out


def _offers(value: str):
    return value if value in ("first", "all") else int(value)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cardmarket", description="Scrape cardmarket.com through Scrape.do (token: SCRAPEDO_TOKEN).")
    p.add_argument("--token", help="Scrape.do token (default: SCRAPEDO_TOKEN)")
    p.add_argument("--out", help="write to this file instead of stdout")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("games", help="list the games")
    s = sub.add_parser("expansions", help="all expansions of a game"); s.add_argument("game")
    s = sub.add_parser("expansion", help="one expansion: id, release date, categories"); s.add_argument("game"); s.add_argument("slug")
    s = sub.add_parser("top", help="weekly best sellers"); s.add_argument("game")

    s = sub.add_parser("list", help="products of a category (100 per page, max 1000)")
    s.add_argument("game"); s.add_argument("--category", default="Singles")
    s.add_argument("--expansion-id", type=int); s.add_argument("--rarity-id", type=int)
    s.add_argument("--sort"); s.add_argument("--only-available", action="store_true"); s.add_argument("--max-pages", type=int)

    s = sub.add_parser("search", help="search products by name")
    s.add_argument("game"); s.add_argument("query"); s.add_argument("--category-id", type=int)
    s.add_argument("--exact", action="store_true"); s.add_argument("--only-available", action="store_true")
    s.add_argument("--sort"); s.add_argument("--max-pages", type=int)

    s = sub.add_parser("catalog", help="every product of a category, expansion by expansion")
    s.add_argument("game"); s.add_argument("--category", default="Singles")
    s.add_argument("--expansion-id", type=int, action="append", help="limit to these expansions (repeatable)")
    s.add_argument("--workers", type=int, default=4)

    for name, helptext in (("product", "product pages with offers (URLs)"), ("card", "all versions of a card with offers")):
        s = sub.add_parser(name, help=helptext)
        if name == "card":
            s.add_argument("game"); s.add_argument("names", nargs="+", help="card slug as in /Cards/<slug>")
        else:
            s.add_argument("urls", nargs="+")
        s.add_argument("--offers", type=_offers, default="all", help='"first" (50), "all" (max 300) or a number')
        s.add_argument("--filter", action="append", metavar="KEY=VALUE", help="offer filter, e.g. language=1,3 minCondition=2 isFoil=Y")
        s.add_argument("--workers", type=int, default=5)

    s = sub.add_parser("versions", help="every printing of a card"); s.add_argument("game"); s.add_argument("name")
    s = sub.add_parser("seller", help="seller profile"); s.add_argument("game"); s.add_argument("username")
    s = sub.add_parser("seller-offers", help="a seller's stock (20 per page, max 2000)")
    s.add_argument("game"); s.add_argument("username"); s.add_argument("--category", default="Singles")
    s.add_argument("--filter", action="append", metavar="KEY=VALUE", help="e.g. isFoil=Y sortBy=price_desc idLanguages=1")
    s.add_argument("--max-pages", type=int)
    return p


def _write(out, data) -> int:
    """A single object -> one JSON line; a list or stream -> one JSON line per item (JSONL).
    Returns how many items were errors."""
    if isinstance(data, dict):
        data = [data]
    errors = 0
    for item in data:
        if isinstance(item, dict) and "error" in item and "input" in item:
            errors += 1
        out.write(json.dumps(item, ensure_ascii=False) + "\n")
        out.flush()
    return errors


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    cm = Cardmarket(args.token)
    c = args.cmd
    if c == "games":
        data = cm.games()
    elif c == "expansions":
        data = cm.expansions(args.game)
    elif c == "expansion":
        data = cm.expansion(args.game, args.slug)
    elif c == "top":
        data = cm.top_cards(args.game)
    elif c == "list":
        data = cm.products(args.game, args.category, expansion_id=args.expansion_id, rarity_id=args.rarity_id,
                           sort=args.sort, only_available=args.only_available, max_pages=args.max_pages)
    elif c == "search":
        data = cm.search(args.game, args.query, category_id=args.category_id, exact=args.exact,
                         only_available=args.only_available, sort=args.sort, max_pages=args.max_pages)
    elif c == "catalog":
        data = cm.catalog(args.game, args.category, expansion_ids=args.expansion_id, workers=args.workers)
    elif c == "product":
        f = _filters(args.filter)
        data = cm.map(lambda u: cm.product(u, offers=args.offers, filters=f), args.urls, workers=args.workers)
    elif c == "card":
        f = _filters(args.filter)
        data = cm.map(lambda n: cm.card(args.game, n, offers=args.offers, filters=f), args.names, workers=args.workers)
    elif c == "versions":
        data = cm.versions(args.game, args.name)
    elif c == "seller":
        data = cm.seller(args.game, args.username)
    else:
        data = cm.seller_offers(args.game, args.username, args.category, filters=_filters(args.filter), max_pages=args.max_pages)

    out = open(args.out, "w", encoding="utf-8") if args.out else sys.stdout
    try:
        errors = _write(out, data)
    finally:
        if args.out:
            out.close()
    errors += len(getattr(cm, "catalog_errors", []))
    print(f"# {cm.http.requests_made} requests, {cm.credits_used} credits, {errors} failed", file=sys.stderr)
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
