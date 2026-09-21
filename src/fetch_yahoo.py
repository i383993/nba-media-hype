"""Download Yahoo Sports NBA closing lines + public betting splits (2021-22 to 2024-25).

Scraped and published by csdurfee/scrape_yahoo_odds (Yahoo's odds endpoint has
since been removed, so these CSVs are the only copy). Output: data/raw/odds_yahoo/
"""
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
SRC = "https://raw.githubusercontent.com/csdurfee/scrape_yahoo_odds/HEAD/yahoo_scrapes/{year}/odds.csv"


def main():
    out = ROOT / "data" / "raw" / "odds_yahoo"
    out.mkdir(parents=True, exist_ok=True)
    for year in (2021, 2022, 2023, 2024):
        r = requests.get(SRC.format(year=year), timeout=60)
        r.raise_for_status()
        (out / f"{year}.csv").write_bytes(r.content)
        print(year, len(r.content.splitlines()) - 1, "games")


if __name__ == "__main__":
    main()
