"""Download raw HTML/XML fixtures through Scrape.do for parser tests.

    SCRAPEDO_TOKEN=... python scripts/capture_fixtures.py

Pages that are followed by a "load more" call share a sessionId with it.
"""
import html
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cardmarket_scrapedo.transport import ScrapeDo, new_session_id

HTTP = ScrapeDo()  # SCRAPEDO_TOKEN, optional SCRAPEDO_API
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
CM = "https://www.cardmarket.com"

PAGES = {
    "magic_home": "/en/Magic",
    "magic_expansions": "/en/Magic/Expansions",
    "magic_expansion": "/en/Magic/Expansions/Modern-Horizons",
    "magic_list": "/en/Magic/Products/Singles/Modern-Horizons?mode=list&perSite=100",
    "magic_list_grid": "/en/Magic/Products/Singles/Modern-Horizons",
    "magic_search": "/en/Magic/Products/Search?searchString=lightning+bolt&mode=list&perSite=100",
    "magic_sealed": "/en/Magic/Products/Booster-Boxes/Modern-Horizons-Booster-Box",
    "magic_versions": "/en/Magic/Cards/Ephemerate/Versions",
    "magic_user": "/en/Magic/Users/ilGiocoliere",  # a professional shop, not a private person
    "magic_user_offers": "/en/Magic/Users/ilGiocoliere/Offers/Singles",
    "magic_top_cards": "/en/Magic/Data/Weekly-Top-Cards",
    "pokemon_expansions": "/en/Pokemon/Expansions",
    "pokemon_list": "/en/Pokemon/Products/Singles/Legendary-Collection?mode=list&perSite=100",
    "ygo_list": "/en/YuGiOh/Products/Singles?mode=list&perSite=100",
    "ygo_product": "/en/YuGiOh/Products/Singles/Magnificent-Monsters/Dark-Magical-Curtain-V1-Ultra-Rare",
}

# page -> (fixture name of the ajax answer, ajax action)
WITH_LOAD_MORE = {
    "magic_product": ("/en/Magic/Products/Singles/Modern-Masters-2015/Combust?language=1&minCondition=4", "Product_LoadMoreArticles"),
    "magic_card": ("/en/Magic/Cards/Ephemerate", "Metacard_LoadMoreArticles"),
    "pokemon_product": ("/en/Pokemon/Products/Singles/Legendary-Collection/Snorlax-LC64", "Product_LoadMoreArticles"),
}


def get(path, sid=None):
    # The library transport retries and keeps the token out of error messages.
    return HTTP.get(CM + path, session_id=sid)


def form_fields(page, action):
    form = re.search(rf'<form[^>]*data-ajax-action="{action}".*?</form>', page, re.S).group(0)
    fields = {}
    for tag in re.findall(r'<input[^>]*type="hidden"[^>]*>', form):
        name = re.search(r'name="([^"]*)"', tag)
        value = re.search(r'value="([^"]*)"', tag)
        if name:
            fields[name.group(1)] = html.unescape(value.group(1)) if value else ""
    return fields


def scrub_buyers(html):
    """Seller pages list recent buyers, who are private people: mask their usernames."""
    table = re.search(r'<table[^>]*id="EvaluationsTable".*?</table>', html, re.S)
    if not table:
        return html
    masked = re.sub(r'<a href="/[^"]*/Users/[^"]+">[^<]+</a>', '<a href="#">buyer</a>', table.group(0))
    return html.replace(table.group(0), masked)


def scrub_contact(html):
    """Shop pages show a contact name and street address: keep only the country line."""
    row = re.search(r'<div id="PersonalInfoRow".*?id="collapsibleAdditionalInfo"', html, re.S)
    if not row:
        return html
    country = re.search(r'title="([^"]+)"[^>]*class="icon"', row.group(0))
    keep = country.group(1) if country else None
    masked = re.sub(r'(<p class="mb-1 w-100">)([^<]*)(</p>)',
                    lambda m: m.group(0) if m.group(2) == keep else m.group(1) + "redacted" + m.group(3), row.group(0))
    return html.replace(row.group(0), masked)


def capture(name, path):
    (OUT / f"{name}.html").write_text(scrub_contact(scrub_buyers(get(path))), encoding="utf-8")
    return name


def capture_with_load_more(name, path, action):
    sid = new_session_id()
    page = get(path, sid)
    (OUT / f"{name}.html").write_text(page, encoding="utf-8")
    game = path.split("/")[2]
    xml = HTTP.post_form(f"{CM}/en/{game}/AjaxAction/{action}", form_fields(page, action), sid)
    (OUT / f"{name}_load_more.xml").write_text(xml, encoding="utf-8")
    return name


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(8) as pool:
        jobs = [pool.submit(capture, n, p) for n, p in PAGES.items()]
        jobs += [pool.submit(capture_with_load_more, n, p, a) for n, (p, a) in WITH_LOAD_MORE.items()]
        for j in jobs:
            print("saved", j.result())
