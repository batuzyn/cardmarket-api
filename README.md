# Cardmarket API for Python: prices, offers & price history without getting blocked

An unofficial **Cardmarket API** and **Cardmarket scraper** for Python. It gets card prices, every seller offer, the price trend, recent price history, expansions, search results and seller profiles from [cardmarket.com](https://www.cardmarket.com). You don't need a Cardmarket API key, a headless browser, or a fight with Cloudflare.

> **TL;DR:** `cardmarket-api` is an open-source Python library and CLI that scrapes Cardmarket (cardmarket.com) through the Scrape.do web scraping API. It returns card prices, all seller offers (up to Cardmarket's 300 limit), price trend and recent price history as JSON. It needs no official Cardmarket API key and avoids Cloudflare `403 Forbidden` blocks without running a browser.

It works for all 22 games on Cardmarket: **Magic: The Gathering, Pokémon, Yu-Gi-Oh!, One Piece, Lorcana, Riftbound, Digimon, Dragon Ball Super, Flesh and Blood, Star Wars Unlimited, Gundam, Final Fantasy TCG, Cardfight!! Vanguard, Weiss Schwarz, Force of Will, Cyberpunk** and more.

```python
from cardmarket_scrapedo import Cardmarket

cm = Cardmarket()   # SCRAPEDO_TOKEN from the environment
card = cm.product("https://www.cardmarket.com/en/Pokemon/Products/Singles/Legendary-Collection/Snorlax-LC64", offers="all")

card["price_trend"], card["avg_30d"], card["from_price"]   # 6.47, 6.02, 1.95
len(card["offers"])                                         # every offer, not just the first 50
card["price_history"][-1]                                   # {'date': '2026-09-25', 'avg_sell_price': 1.0}
```

## Tested output

Every flow below was run against the live site, and the files are the unedited output. See [`examples/results/`](examples/results/); it is regenerated with [`examples/run_examples.py`](examples/run_examples.py).

| Call | Result | Requests | Output |
|---|---|---|---|
| Magic single, `offers="all"` | 300 offers (site max) + 30 price points | 6 | [JSON](examples/results/product_all_offers_magic.json) · [CSV](examples/results/offers_magic.csv) |
| Pokémon single, English + Near Mint filter | 16 offers | 1 | [JSON](examples/results/product_filtered_pokemon.json) |
| Sealed booster box | 50 offers | 1 | [JSON](examples/results/product_sealed_booster_box.json) |
| Yu-Gi-Oh! card across all printings | 100 offers from 9 versions | 2 | [JSON](examples/results/card_all_versions_ygo.json) |
| Every printing of a card | 12 versions | 1 | [JSON](examples/results/versions_magic.json) |
| Search `charizard` (Pokémon) | 100 products | 1 | [JSONL](examples/results/search_pokemon_charizard.jsonl) |
| Whole expansion (Modern Horizons) | 337 products | 4 | [JSONL](examples/results/list_expansion_magic.jsonl) |
| One Piece expansions | 152 expansions | 1 | [JSON](examples/results/expansions_onepiece.json) |
| Lorcana weekly best sellers | 100 products | 1 | [JSON](examples/results/top_cards_lorcana.json) |
| Seller profile / seller stock (foils) | 10 categories / 40 offers | 1 / 2 | [JSON](examples/results/seller_profile.json) · [JSONL](examples/results/seller_offers_foil.jsonl) |

Full table with timings and credits: [examples/results/SUMMARY.md](examples/results/SUMMARY.md).

**Larger benchmark:** [970 Magic cards with 30 workers](examples/results/FOIL_SPLIT_BENCHMARK.md): every offer of each card, with tables that hit the 300-row cap split into foil and non-foil. 97.3% succeeded on the first pass, in 12 minutes, collecting 144,008 offers.

One offer from that output:

```json
{
  "id": 752594833,
  "seller": {"name": "ilGiocoliere", "type": "Professional", "country": "Italy", "sales": 22268, "available_items": 89164},
  "condition": "Near Mint", "condition_code": "NM", "language": "English",
  "is_foil": false, "is_first_edition": false, "comments": null,
  "price": 0.02, "currency": "EUR", "quantity": 3
}
```

## Sponsor

[![Scrape.do](.github/assets/scrapedo.gif)](https://scrape.do/?utm_source=github&utm_medium=repo_cardmarket)

---

## How to fix Cloudflare `403 Forbidden` on Cardmarket (Python)

Cardmarket runs behind Cloudflare. A plain `requests.get("https://www.cardmarket.com/...")` gets a **403** or the **"Just a moment..." / "Checking your browser"** challenge page instead of HTML. The usual workarounds fail for well-known reasons:

| What people try | What happens on Cardmarket |
|---|---|
| `requests` / `httpx` / `curl` | 403 or the challenge page: the TLS fingerprint and headers are not a browser's |
| `cloudscraper`, `cfscrape` | Built for older Cloudflare challenges. They usually fail on current ones |
| Selenium / Playwright / Puppeteer | Automation is often detected, and a browser per request is slow and costly at scale |
| FlareSolverr, `cf_clearance` cookies | The cookie is tied to one IP and browser fingerprint and expires, so reusing it breaks |
| Rotating datacenter proxies | Datacenter IP ranges are commonly blocked |
| "Show more results" with `requests` | Returns *"The form has expired"*: the form token belongs to the visitor who loaded the page |

This library sends every request through **[Scrape.do](https://scrape.do/?utm_source=github&utm_medium=repo_cardmarket)**, a web scraping API that handles Cloudflare, residential IPs and browser fingerprints. You get the real Cardmarket HTML back, usually in a few seconds, without running a browser. The library then turns that HTML into clean JSON.

It also handles the part most Cardmarket scrapers get wrong: **loading all offers**. A product page shows 50 offers. The rest are behind "Show more results", which only works for the same visitor that opened the page. The library keeps the page and every "load more" call on one Scrape.do session (`sessionId`), so you get all of them, up to Cardmarket's 300-offer limit.

## Why not the official Cardmarket API? (a Cardmarket API alternative)

The official Cardmarket API needs registered app credentials (OAuth keys) before you can make a single call. This library needs no Cardmarket account and no API key. It reads the same public pages you see in the browser, so it can return things like the full offer list, seller profiles and the price chart data shown on each product page.

---

## Install

```bash
pip install git+https://github.com/batuzyn/cardmarket-api.git
export SCRAPEDO_TOKEN=your_token
```

Get your token from **[Scrape.do](https://scrape.do/?utm_source=github&utm_medium=repo_cardmarket)**.

Python 3.9+. Dependencies: `requests`, `beautifulsoup4`, `lxml`. The package installs as `cardmarket-scrapedo`; import it as `cardmarket_scrapedo` and use the `cardmarket` command. It reads the English site (`/en/`).

## What you can get

| Data | Python | CLI |
|---|---|---|
| **Card price, price trend, 30/7/1-day averages, price history** and all offers | `cm.product(url, offers="all")` | `cardmarket product URL` |
| **All offers across every printing of a card** | `cm.card("Magic", "Ephemerate", offers="all")` | `cardmarket card Magic Ephemerate` |
| Every printing / version of a card | `cm.versions("Magic", "Ephemerate")` | `cardmarket versions Magic Ephemerate` |
| **Search** cards and sealed products | `cm.search("Pokemon", "charizard")` | `cardmarket search Pokemon charizard` |
| Product lists by category / expansion / rarity | `cm.products("Magic", "Singles", expansion_id=2440)` | `cardmarket list Magic --expansion-id 2440` |
| **Full catalogue export** of a game (all expansions) | `cm.catalog("YuGiOh")` | `cardmarket catalog YuGiOh` |
| Expansions / sets with release dates | `cm.expansions("OnePiece")` | `cardmarket expansions OnePiece` |
| One expansion: id, card count, categories | `cm.expansion("Magic", "Modern-Horizons")` | `cardmarket expansion Magic Modern-Horizons` |
| **Seller profile**: rating, sales, evaluations | `cm.seller("Magic", "<seller>")` | `cardmarket seller Magic <seller>` |
| A seller's stock, filterable | `cm.seller_offers("Magic", "<seller>", filters={"isFoil": "Y"})` | `cardmarket seller-offers Magic <seller>` |
| Weekly best sellers | `cm.top_cards("Lorcana")` | `cardmarket top Lorcana` |
| All games | `cm.games()` | `cardmarket games` |

## Examples

### Cardmarket price tracker: price trend and history for a list of cards

```python
urls = [
    "https://www.cardmarket.com/en/Magic/Products/Singles/Modern-Horizons/Ephemerate",
    "https://www.cardmarket.com/en/YuGiOh/Products/Singles/Magnificent-Monsters/Dark-Magical-Curtain-V1-Ultra-Rare",
]
for p in cm.map(lambda u: cm.product(u), urls, workers=5):
    print(p["name"], p["from_price"], p["price_trend"], p["avg_30d"], len(p["price_history"]))
```

### All offers of a card, filtered: English, Near Mint or better, German sellers

```python
url = "https://www.cardmarket.com/en/Magic/Products/Singles/Modern-Horizons/Ephemerate"
p = cm.product(url, offers="all", filters={"language": "1", "minCondition": 2, "sellerCountry": "7"})
if p["offers"]:
    cheapest = min(p["offers"], key=lambda o: o["price"])
    print(cheapest["price"], cheapest["seller"]["name"], cheapest["condition"])
```

### Export a whole game to CSV / JSONL

```bash
cardmarket --out pokemon-singles.jsonl catalog Pokemon
cardmarket --out lorcana-sealed.jsonl catalog Lorcana --category Booster-Boxes
```

### Every offer of many cards, splitting foil / non-foil past the 300-row cap

```bash
python examples/foil_split.py urls.txt --workers 30 --out results.jsonl
```

See the [benchmark](examples/results/FOIL_SPLIT_BENCHMARK.md) for what it does and how it performed on 970 cards.

### Offers of many cards into one CSV

```bash
python examples/offers_to_csv.py URL1 URL2 URL3 > offers.csv
```

The CLI prints JSON: one line per result, JSONL for lists. At the end it reports on stderr how many requests and credits were used and how many items failed; the exit code is 1 if any failed.

**Offers default:** in Python `offers` defaults to `"first"` (the first 50, one request); the CLI defaults to `--offers all`.

## Offer filters

Pass them as `filters={...}` or with `--filter key=value`. They are Cardmarket's own URL parameters:

| Filter | Example | Meaning |
|---|---|---|
| `language` | `1,3` | language ids (each result lists them under `filters.language`) |
| `minCondition` | `2` | 1 Mint, 2 Near Mint, 3 Excellent, 4 Good, 5 Light Played, 6 Played, 7 Poor |
| `sellerCountry` | `7,12` | seller country ids |
| `sellerType` | `1,2` | 0 private, 1 professional, 2 powerseller |
| `isFoil` / `isSigned` / `isAltered` | `Y` / `N` | Magic and most games |
| `isFirstEd` / `isReverseHolo` | `Y` / `N` | Pokémon, Yu-Gi-Oh! |
| `amount` | `4` | minimum quantity |

The ids differ per game. Every product result includes `filters` with the exact options that page accepts.

## Output

**Product** (`cm.product`):

```
id, name, url, game, category, expansion, expansion_url, rarity, number, image, rules_text,
available_items, from_price, price_trend, avg_30d, avg_7d, avg_1d, currency,
price_history[{date, avg_sell_price}], versions_url, all_offers_url, attributes{...},
filters{...}, offers[...], offers_complete
```

**Offer**:

```
id, price, quantity, condition, condition_code, language,
is_foil, is_signed, is_altered, is_playset, is_first_edition, is_reverse_holo,
comments, scan_image, price_original, currency,
seller{name, url, type, country, sales, available_items},   # null on seller-stock pages
product{name, url, expansion, expansion_url, rarity, image} # seller-stock pages; card-wide pages give expansion, rarity and image only
```

**List row** (`products`, `search`, `catalog`):

```
id, name, url, expansion, rarity, number, available_items, from_price,
available_foils, from_price_foil, image
```

**Card across all printings** (`cm.card`): `id, name, url, game, available_items, version_count, from_price, price_trend, currency, attributes, offers[...], offers_complete`.

Prices are floats in EUR, as Cardmarket shows them. `price_history` has one point per day *with sales*, the last 30 of them, so for slow-selling cards it can reach back several months.

## Limits Cardmarket puts on its pages (and how the library handles them)

- **Offers:** Cardmarket rate-limits rapid "Show more results" clicks, so the library spaces them out (`click_delay`, default ~1 s). After a failed click it waits (`retry_backoff`), reloads the page and continues from the page that failed (`flow_retries`, default 3). Cardmarket shows at most 300 offers per product. `offers="all"` loads up to that in 6 requests (plus retries if a request fails). `offers_complete` is `true` only when the result holds every offer the product has; it is `false` when you set a limit, stopped at the first page, or hit the 300 cap.
- **Product lists and search:** 100 per page, at most 10 pages, so 1000 results per query. `catalog()` goes expansion by expansion. An expansion that reaches 1000 is read per rarity and by name A–Z and Z–A (which also catches products without a rarity), then de-duplicated. Expansions that fail are skipped and listed in `cm.catalog_errors`.
- **Seller stock:** 20 per page, at most 100 pages (2000 offers). Narrow it with filters such as `idExpansions`, `idRarities`, `minPrice` and `maxPrice`.
- **Search with one match:** Cardmarket redirects straight to the product. `search()` returns it as a single result.

## Cost

Each request is one Scrape.do call with `super=true`, typically 10 credits:

| Call | Requests |
|---|---|
| product page, first 50 offers | 1 |
| product with all offers (up to 300) | up to 6 |
| list or search page (100 products) | 1 |
| full expansion of 300 cards | 3–4 |

`cm.credits_used` and the CLI's final line show what a run actually used (read from Scrape.do's response headers).

## FAQ

**Is there a Cardmarket API alternative without an API key?**
Yes, this library. It reads the public site, so you only need a Scrape.do token.

**Is there a Cardmarket API?**
Yes: the official one needs registered API credentials. This project is an unofficial alternative that reads the public website through Scrape.do. No Cardmarket account or API key is needed.

**How do I get Cardmarket price history?**
Every product page contains the average sell price chart (one point per day with sales). `cm.product(url)["price_history"]` returns it as `[{date, avg_sell_price}]`, together with `price_trend`, `avg_30d`, `avg_7d` and `avg_1d`.

**Is Cardmarket down, or am I blocked?**
If the site works in your browser but your script gets `403 Forbidden` or a "Just a moment..." page, Cardmarket is not down. Cloudflare is blocking the script. Requests through Scrape.do get the normal page.

**What does "403 Forbidden" from Cloudflare mean?**
Cloudflare decided the request is not from a regular visitor, usually because of the IP range (datacenter or cloud), the TLS/HTTP fingerprint of the client library, or missing browser behaviour. It is a block, not a missing page.

**How do I bypass Cloudflare 403 Forbidden in Python for Cardmarket?**
Send the request through a scraping API that handles Cloudflare instead of trying to imitate a browser yourself. With this library that is automatic: `Cardmarket().product(url)`. For your own requests, call `https://api.scrape.do/?token=...&super=true&url=<cardmarket url>`.

**Why does Cardmarket return 403 to my Python script?**
Cloudflare blocks requests that don't look like a real browser on a residential connection. See [the table above](#how-to-fix-cloudflare-403-forbidden-on-cardmarket-python). Routing requests through Scrape.do solves it without a browser.

**Why do I only get 50 offers?**
The rest are behind "Show more results", and that form only works for the visitor who opened the page. Use `offers="all"`; the library keeps both on one session.

**Can I scrape Pokémon, MTG, Yu-Gi-Oh! and One Piece prices?**
Yes, all 22 games on Cardmarket use the same flows. Game-specific fields (Pokémon species, first edition, reverse holo) are included.

**How fast is it?**
Usually a few seconds per page; see the timings in [SUMMARY.md](examples/results/SUMMARY.md). Different products run in parallel with `cm.map(..., workers=N)`.

## Development

```bash
uv venv && uv pip install -e ".[dev]"
uv run pytest                                          # parsers and flows, offline
SCRAPEDO_TOKEN=... RUN_LIVE=1 uv run pytest -m live    # against the real site
SCRAPEDO_TOKEN=... uv run python examples/run_examples.py   # refresh examples/results
SCRAPEDO_TOKEN=... python scripts/check_endpoints.py   # every flow, every game
SCRAPEDO_TOKEN=... python scripts/capture_fixtures.py  # refresh the HTML fixtures
```

The parsers are tested against raw Cardmarket HTML captured through Scrape.do (`tests/fixtures`). If Cardmarket changes its markup, refresh the fixtures and run the tests.

## Support

- **Problems with this library** (a parser broke, a field is wrong, a flow is missing): [open an issue](https://github.com/batuzyn/cardmarket-api/issues).
- **Blocked requests, credits, higher volume, or scraping another site:** contact the Scrape.do team at [support@scrape.do](mailto:support@scrape.do) or through [scrape.do](https://scrape.do/?utm_source=github&utm_medium=repo_cardmarket).

## License

MIT, see [LICENSE](LICENSE).

## Disclaimer

This project is not affiliated with, endorsed by, or connected to Cardmarket (Sammelkartenmarkt GmbH & Co. KG). It reads publicly available pages. Use it responsibly and in line with Cardmarket's terms and the laws that apply to you.

---

<p align="center">
  <a href="https://scrape.do/?utm_source=github&utm_medium=repo_cardmarket"><img src=".github/assets/scrapedo.gif" alt="Scrape.do: web scraping API that handles Cloudflare" width="600"></a><br>
  <sub>Scraping another site that blocks you? <a href="https://scrape.do/?utm_source=github&utm_medium=repo_cardmarket">Scrape.do</a> handles Cloudflare and other anti-bot systems.</sub>
</p>
