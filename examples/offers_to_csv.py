"""All offers of some products into one CSV.

    SCRAPEDO_TOKEN=... python examples/offers_to_csv.py URL [URL ...] > offers.csv
"""
import csv
import sys

from cardmarket_scrapedo import Cardmarket

cm = Cardmarket()
out = csv.writer(sys.stdout)
out.writerow(["product", "price", "quantity", "condition", "language", "foil", "seller", "seller_type", "country", "comments"])

for p in cm.map(lambda url: cm.product(url, offers="all"), sys.argv[1:], workers=5):
    if "error" in p:
        print(f"failed: {p['input']}: {p['error']}", file=sys.stderr)
        continue
    for o in p["offers"]:
        s = o["seller"] or {}
        out.writerow([p["name"], o["price"], o["quantity"], o["condition_code"], o["language"], o["is_foil"],
                      s.get("name"), s.get("type"), s.get("country"), o["comments"]])

print(f"{cm.http.requests_made} requests, {cm.credits_used} credits", file=sys.stderr)
