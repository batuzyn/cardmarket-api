"""Get every offer of many Magic cards, splitting tables that hit Cardmarket's 300-row cap.

    SCRAPEDO_TOKEN=... python examples/foil_split.py urls.txt --workers 15 --out results.jsonl

A product table shows at most 300 offers, sorted by price. Foil offers are usually
more expensive, so on popular cards they sit past row 300 and never show up.

For each URL:
  1. Add the filters (country, seller type, language, condition ...) to shrink the table.
  2. Load it with every "Show more results" click (50 + up to 5 x 50 rows).
  3. Fewer than 300 rows: that is the whole table.
     Exactly 300 rows: the cap was hit, so load it again twice, with isFoil=N and isFoil=Y.

Each line of the output is one input URL: its row counts, whether it was split,
what it cost, and the offers themselves.
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from cardmarket_scrapedo import Cardmarket

CAP = 300
DEFAULT_FILTERS = {
    "sellerCountry": "1,2,35,6,8,12,7,14,15,17,20,23,25,26,31,30,10,28",
    "sellerType": "1,2",
    "language": "1",
    "minCondition": "4",
    "isSigned": "N",
    "isAltered": "N",
}


def load(cm, url, filters):
    p = cm.product(url, offers="all", filters=filters)
    return {"url": cm.url(url, **filters), "rows": len(p["offers"]), "capped": len(p["offers"]) >= CAP,
            "attempts": p.get("attempts", 1), "offers": p["offers"]}


def scrape(url, filters):
    cm = Cardmarket()   # one per URL so requests and credits are counted per URL
    t = time.time()
    out = {"input": url, "status": None, "tables": [], "requests": 0, "credits": 0, "seconds": 0, "error": None}
    try:
        table = load(cm, url, filters)
        if not table["capped"]:
            out["status"] = "complete"
            out["tables"] = [table]
        else:
            out["status"] = "split"
            out["tables"] = [load(cm, url, dict(filters, isFoil=f)) for f in ("N", "Y")]
            if any(t["capped"] for t in out["tables"]):
                out["status"] = "split_still_capped"   # needs more filters (e.g. per language)
    except Exception as e:
        out["status"] = "error"
        out["error"] = f"{type(e).__name__}: {e}"
    out.update(requests=cm.http.requests_made, credits=cm.credits_used, seconds=round(time.time() - t, 1))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("urls", help="text file, one product URL per line")
    ap.add_argument("--workers", type=int, default=15)
    ap.add_argument("--out", default="foil_split_results.jsonl")
    ap.add_argument("--no-filters", action="store_true", help="do not add the default filters")
    args = ap.parse_args()

    urls = [u.strip() for u in open(args.urls, encoding="utf-8") if u.strip()]
    filters = {} if args.no_filters else DEFAULT_FILTERS
    started = time.time()
    counts = {}
    with ThreadPoolExecutor(args.workers) as pool, open(args.out, "w", encoding="utf-8") as out:
        futures = [pool.submit(scrape, u, filters) for u in urls]
        for i, f in enumerate(as_completed(futures), 1):
            r = f.result()
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
            out.flush()
            if i % 50 == 0 or i == len(urls):
                print(f"{i}/{len(urls)} {counts} {time.time() - started:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
