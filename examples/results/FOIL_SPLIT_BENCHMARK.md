# Benchmark: 970 Magic cards, every offer, foil / non-foil split

A real run of [`examples/foil_split.py`](../foil_split.py) on 970 Magic: The Gathering product URLs, through the Scrape.do API, on 2026-09-26/27.

## The problem it solves

A Cardmarket product table shows at most **300 offers**, sorted by price. Foil printings are usually more expensive, so on popular cards the foil offers sit past row 300 and never show up.

For each URL the script:

1. Adds filters to shrink the table: EU seller countries, professional and powerseller sellers, English, condition Good or better, not signed, not altered.
2. Loads the full table: the first 50 rows, then up to 5 "Show more results" clicks.
3. If the table has **fewer than 300 rows**, it is complete. If it has **exactly 300**, the cap was hit, so the script loads it again twice: with `isFoil=N` (non-foil) and `isFoil=Y` (foil).

```bash
SCRAPEDO_TOKEN=... python examples/foil_split.py urls.txt --workers 30 --out results.jsonl
```

## Results (30 concurrent workers)

| | |
|---|---|
| URLs | 970 |
| Wall time | **722 s** (12 min) |
| Scraped on the first pass | **944 / 970 (97.3%)** |
| Offer rows collected | **144,008** |
| Requests / credits | 6,182 / 53,160 (≈ 55 credits per URL) |
| Median time per URL | 9.2 s |

What the tables looked like:

| Outcome | URLs | |
|---|---|---|
| Complete in one table (< 300 rows) | 793 | 7 empty, 251 with 1–50 rows, 330 with 51–150, 205 with 151–299 |
| Hit 300 → split, both halves < 300 | 67 | complete non-foil and foil tables |
| Hit 300 → split, non-foil still 300 | 84 | foil side complete; non-foil needs one more filter (e.g. per country or language) |
| Failed after 4 attempts | 26 | Cardmarket rate limits (429) on "Show more results"; a retry pass later recovers most |

The split recovered **18,468 foil offers** that are invisible in the unsplit tables. No foil half ever hit 300.

Sample rows: [foil_split_sample.csv](foil_split_sample.csv). One full result line, cut to 2 offers per table: [foil_split_sample_result.json](foil_split_sample_result.json).

## What made 30 workers work

The same 970 URLs were run three times:

| | 15 workers | 30 workers, no pacing | **30 workers, paced (current)** |
|---|---|---|---|
| Failed on first pass | 5.8% | 26.9% | **2.7%** |
| Successful URLs per second | 0.99 | 1.27 | **1.31** |
| Cards that hit 300 and were split | 145 | 17 | **151** |
| Offer rows collected | 135,419 | 56,850 | **144,008** |

Without pacing, Cardmarket rate-limits rapid "Show more results" clicks, and at 30 workers the large cards (the ones that need the most clicks) failed first. That is why only 17 cards got split in that run. The library now:

- **spaces out clicks** (`click_delay`, default 1.0–1.5 s),
- **waits before recovering** from a failed click (`retry_backoff`: 3 s, 6 s, 9 s … plus jitter),
- **reloads the page and continues from the page that failed**, not from the first page. The form token is tied to the visitor, so a fresh page is needed, but already loaded offers are kept (de-duplicated by offer id).

27% of the tables in the paced run needed more than one attempt (233 needed 2, 104 needed 3, 31 needed 4). They came back complete instead of failing.

```python
cm = Cardmarket(click_delay=1.0, retry_backoff=3.0, flow_retries=3)   # the defaults
```

## Planning a larger run

At the measured rate (1.31 successful URLs per second with 30 workers), **100,000 URLs take about 21 hours** and about 5.5M credits. Add a retry pass at the end for the ~3% that fail. Real numbers depend on the card mix: popular cards have more offers, need more clicks and get split more often.
