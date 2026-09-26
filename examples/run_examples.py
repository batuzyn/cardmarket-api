"""Run every flow once against the live site and save the output to examples/results/.

    SCRAPEDO_TOKEN=... python examples/run_examples.py

The files in examples/results/ are real output of this script, so you can see what
each call returns before you run anything. SUMMARY.md lists what ran, how many
items came back and what it cost.
"""
import csv
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from cardmarket_scrapedo import Cardmarket

OUT = Path(__file__).resolve().parent / "results"
CM = "https://www.cardmarket.com/en"


def save(name, data):
    path = OUT / name
    if name.endswith(".jsonl"):
        path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in data), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def offers_csv(name, product):
    path = OUT / name
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["price", "quantity", "condition", "language", "foil", "first_edition", "seller", "seller_type", "country"])
        for o in product["offers"]:
            s = o["seller"] or {}
            w.writerow([o["price"], o["quantity"], o["condition_code"], o["language"], o["is_foil"], o["is_first_edition"],
                        s.get("name"), s.get("type"), s.get("country")])
    return path


# (file, what it shows, python call, how to count the result)
EXAMPLES = [
    ("product_all_offers_magic.json", "Magic single, all offers (site max 300) + price history",
     lambda cm: cm.product(f"{CM}/Magic/Products/Singles/Modern-Masters-2015/Combust", offers="all"),
     lambda r: f'{len(r["offers"])} offers, {len(r["price_history"])} price points'),
    ("product_filtered_pokemon.json", "Pokémon single, English + Near Mint or better",
     lambda cm: cm.product(f"{CM}/Pokemon/Products/Singles/Legendary-Collection/Snorlax-LC64", offers="all",
                           filters={"language": "1", "minCondition": 2}),
     lambda r: f'{len(r["offers"])} offers'),
    ("product_sealed_booster_box.json", "Sealed product (booster box), first page",
     lambda cm: cm.product(f"{CM}/Magic/Products/Booster-Boxes/Modern-Horizons-Booster-Box"),
     lambda r: f'{len(r["offers"])} offers'),
    ("card_all_versions_ygo.json", "Yu-Gi-Oh! card across all printings, 100 offers",
     lambda cm: cm.card("YuGiOh", "Dark-Magical-Curtain", offers=100),
     lambda r: f'{len(r["offers"])} offers, {r["version_count"]} versions'),
    ("versions_magic.json", "Every printing of a card",
     lambda cm: cm.versions("Magic", "Ephemerate"),
     lambda r: f'{len(r["versions"])} versions'),
    ("search_pokemon_charizard.jsonl", "Search, first page",
     lambda cm: list(cm.search("Pokemon", "charizard", max_pages=1)),
     lambda r: f"{len(r)} products"),
    ("list_expansion_magic.jsonl", "One expansion, every card (list view)",
     lambda cm: list(cm.products("Magic", expansion_id=2440)),
     lambda r: f"{len(r)} products"),
    ("expansions_onepiece.json", "All One Piece expansions",
     lambda cm: cm.expansions("OnePiece"),
     lambda r: f"{len(r)} expansions"),
    ("expansion_magic.json", "One expansion: id, release date, categories",
     lambda cm: cm.expansion("Magic", "Modern-Horizons"),
     lambda r: f'{len(r["categories"])} categories'),
    ("top_cards_lorcana.json", "Weekly best sellers",
     lambda cm: cm.top_cards("Lorcana"),
     lambda r: f"{len(r)} products"),
    ("seller_profile.json", "Seller profile (a professional shop)",
     lambda cm: cm.seller("Magic", "ilGiocoliere"),
     lambda r: f'{len(r["offer_categories"])} categories, {len(r["recent_evaluations"])} evaluations'),
    ("seller_offers_foil.jsonl", "Seller stock filtered to foils, most expensive first, 2 pages",
     lambda cm: list(cm.seller_offers("Magic", "ilGiocoliere", filters={"isFoil": "Y", "sortBy": "price_desc"}, max_pages=2)),
     lambda r: f"{len(r)} offers"),
    ("games.json", "All games on Cardmarket",
     lambda cm: cm.games(),
     lambda r: f"{len(r)} games"),
]


def run(example):
    name, what, call, count = example
    cm = Cardmarket()
    t = time.time()
    try:
        result = call(cm)
    except Exception as e:
        return {"file": name, "what": what, "error": f"{type(e).__name__}: {e}"}
    save(name, result)
    if name == "product_all_offers_magic.json":
        offers_csv("offers_magic.csv", result)
    return {"file": name, "what": what, "result": count(result), "seconds": round(time.time() - t, 1),
            "requests": cm.http.requests_made, "credits": cm.credits_used}


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    with ThreadPoolExecutor(6) as pool:
        rows = list(pool.map(run, EXAMPLES))
    when = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Example results",
        "",
        f"Real output of [`run_examples.py`](../run_examples.py), run on {when} through the Scrape.do API.",
        "Each file is exactly what the library returned.",
        "",
        "| File | What | Result | Requests | Credits | Time |",
        "|---|---|---|---|---|---|",
    ]
    for r in rows:
        if "error" in r:
            lines.append(f'| {r["file"]} | {r["what"]} | failed: {r["error"][:80]} | | | |')
        else:
            lines.append(f'| [{r["file"]}]({r["file"]}) | {r["what"]} | {r["result"]} | {r["requests"]} | {r["credits"]} | {r["seconds"]}s |')
    lines.append("| [offers_magic.csv](offers_magic.csv) | The Magic offers above as CSV | | | | |")
    total_req = sum(r.get("requests", 0) for r in rows)
    total_cr = sum(r.get("credits", 0) for r in rows)
    lines += ["", f"Total: {total_req} requests, {total_cr} credits."]
    (OUT / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
