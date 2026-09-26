# Example results

Real output of [`run_examples.py`](../run_examples.py), run on 2026-09-26 10:31 UTC through the Scrape.do API.
Each file is exactly what the library returned.

| File | What | Result | Requests | Credits | Time |
|---|---|---|---|---|---|
| [product_all_offers_magic.json](product_all_offers_magic.json) | Magic single, all offers (site max 300) + price history | 300 offers, 30 price points | 6 | 60 | 25.5s |
| [product_filtered_pokemon.json](product_filtered_pokemon.json) | Pokémon single, English + Near Mint or better | 16 offers | 1 | 10 | 1.4s |
| [product_sealed_booster_box.json](product_sealed_booster_box.json) | Sealed product (booster box), first page | 50 offers | 1 | 10 | 1.7s |
| [card_all_versions_ygo.json](card_all_versions_ygo.json) | Yu-Gi-Oh! card across all printings, 100 offers | 100 offers, 9 versions | 2 | 20 | 2.4s |
| [versions_magic.json](versions_magic.json) | Every printing of a card | 12 versions | 1 | 10 | 2.0s |
| [search_pokemon_charizard.jsonl](search_pokemon_charizard.jsonl) | Search, first page | 100 products | 1 | 10 | 3.4s |
| [list_expansion_magic.jsonl](list_expansion_magic.jsonl) | One expansion, every card (list view) | 337 products | 4 | 40 | 12.6s |
| [expansions_onepiece.json](expansions_onepiece.json) | All One Piece expansions | 152 expansions | 1 | 10 | 3.2s |
| [expansion_magic.json](expansion_magic.json) | One expansion: id, release date, categories | 8 categories | 1 | 10 | 1.3s |
| [top_cards_lorcana.json](top_cards_lorcana.json) | Weekly best sellers | 100 products | 1 | 10 | 1.7s |
| [seller_profile.json](seller_profile.json) | Seller profile (a professional shop) | 10 categories, 20 evaluations | 1 | 10 | 5.2s |
| [seller_offers_foil.jsonl](seller_offers_foil.jsonl) | Seller stock filtered to foils, most expensive first, 2 pages | 40 offers | 2 | 20 | 34.0s |
| [games.json](games.json) | All games on Cardmarket | 22 games | 1 | 10 | 2.7s |
| [offers_magic.csv](offers_magic.csv) | The Magic offers above as CSV | | | | |

Total: 23 requests, 230 credits.
