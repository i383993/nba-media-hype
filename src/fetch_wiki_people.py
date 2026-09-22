"""Wikipedia pageviews for every award candidate (players and coaches).

1. Resolve each candidate name in data/raw/awards.csv to its English-Wikipedia article
   (following redirects; a short-description check makes sure it is the basketball person).
2. Download that article's daily pageviews (human users), July 2015 - Sep 2026.

Outputs: data/raw/wiki_titles.csv and data/raw/wiki_people/<title>.csv
Resumable: skips titles already downloaded.
"""
import re
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = RAW / "wiki_people"
HEADERS = {"User-Agent": "sloan-interviews-research/0.1 (academic sports analytics project)"}
API = "https://en.wikipedia.org/w/api.php"
VIEWS = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
         "all-access/user/{title}/daily/20150701/20260920")


def get(url, **params):
    for attempt in range(6):
        r = requests.get(url, params=params or None, headers=HEADERS, timeout=60)
        if r.status_code != 429:
            return r
        time.sleep(30 * (attempt + 1))
    return r


def resolve(name):
    """Return (title, shortdesc) of the basketball person called `name`, or (None, reason)."""
    r = get(API, action="query", titles=name, redirects=1, prop="description", format="json")
    page = next(iter(r.json()["query"]["pages"].values()))
    desc = page.get("description", "") or ""
    if "missing" not in page and "basketball" in desc.lower():
        return page["title"], desc
    # fall back to search ("Name basketball") and take the first hit that is a basketball person
    r = get(API, action="query", list="search", srsearch=f"{name} basketball", srlimit=5, format="json")
    for hit in r.json()["query"]["search"]:
        d = next(iter(get(API, action="query", titles=hit["title"], redirects=1, prop="description",
                          format="json").json()["query"]["pages"].values())).get("description", "") or ""
        if "basketball" in d.lower() and name.split()[-1].lower() in hit["title"].lower():
            return hit["title"], d
    return None, desc or "not found"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    awards = pd.read_csv(RAW / "awards.csv")
    names = sorted(awards.name_key.dropna().unique())
    tpath = RAW / "wiki_titles.csv"
    known = pd.read_csv(tpath) if tpath.exists() else pd.DataFrame(columns=["name_key", "title", "shortdesc"])
    done = set(known.name_key)
    rows = known.to_dict("records")
    for i, name in enumerate(names):
        if name in done:
            continue
        title, desc = resolve(name)
        rows.append({"name_key": name, "title": title, "shortdesc": desc})
        pd.DataFrame(rows).to_csv(tpath, index=False)
        time.sleep(0.3)
        if i % 50 == 0:
            print(f"resolved {i}/{len(names)}", flush=True)
    titles = pd.DataFrame(rows)
    print("unresolved:", titles[titles.title.isna()].name_key.tolist())

    for title in titles.title.dropna().unique():
        path = OUT / (re.sub(r"[^\w\-]", "_", title) + ".csv")
        if path.exists():
            continue
        r = get(VIEWS.format(title=requests.utils.quote(title.replace(" ", "_"), safe="")))
        if r.status_code == 404:  # no recorded views (very new article)
            pd.DataFrame(columns=["date", "views"]).to_csv(path, index=False)
            continue
        r.raise_for_status()
        df = pd.DataFrame(r.json()["items"])
        df["date"] = pd.to_datetime(df.timestamp.str[:8]).dt.date
        df[["date", "views"]].to_csv(path, index=False)
        print("views", title, len(df), flush=True)
        time.sleep(3)
    print("DONE")


if __name__ == "__main__":
    main()
