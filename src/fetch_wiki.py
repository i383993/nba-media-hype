"""Daily English-Wikipedia pageviews per NBA team article (human users only).

A direct measure of public (crowd) attention, complementary to GDELT's measure
of what journalists write. Output: data/raw/wiki/<ABBR>.csv (date, views)
"""
import time
from pathlib import Path

import pandas as pd
import requests

from teams import TEAMS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "wiki"
URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
       "all-access/user/{article}/daily/20150701/20260920")
# Wikimedia asks API clients to identify themselves
HEADERS = {"User-Agent": "sloan-interviews-research/0.1 (academic sports analytics project)"}


def article(query):
    return query.strip('"').replace(" ", "_")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for abbr, info in TEAMS.items():
        if (OUT / f"{abbr}.csv").exists():
            continue
        for attempt in range(6):
            r = requests.get(URL.format(article=article(info["query"])), headers=HEADERS, timeout=60)
            if r.status_code != 429:
                break
            time.sleep(30 * (attempt + 1))
        r.raise_for_status()
        df = pd.DataFrame(r.json()["items"])
        df["date"] = pd.to_datetime(df.timestamp.str[:8]).dt.date
        df[["date", "views"]].to_csv(OUT / f"{abbr}.csv", index=False)
        print(abbr, len(df), flush=True)
        time.sleep(3)


if __name__ == "__main__":
    main()
