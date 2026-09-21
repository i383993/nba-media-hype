"""Download daily news coverage (article volume + average tone) per NBA team from GDELT.

GDELT DOC 2.0 API, English-language sources. Resumable: skips teams already on
disk. GDELT locks you out for a few minutes if requests come faster than about
one per 5 s, so we wait between calls and back off on the rate-limit message.

Output: data/raw/gdelt/<ABBR>_<series>.csv with columns date, value
"""
import sys
import time
import urllib.parse
from io import StringIO
from pathlib import Path

import pandas as pd
import requests

from teams import TEAMS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "raw" / "gdelt"
API = "https://api.gdeltproject.org/api/v2/doc/doc"
START, END = "20180801000000", "20260920000000"
SERIES = {"tone": "timelinetone", "volraw": "timelinevolraw"}


def fetch(query, mode):
    params = {
        "query": f"{query} sourcelang:english",
        "mode": mode,
        "startdatetime": START,
        "enddatetime": END,
        "format": "csv",
    }
    url = f"{API}?{urllib.parse.urlencode(params, quote_via=urllib.parse.quote)}"
    for attempt in range(30):
        time.sleep(120 if attempt == 0 else 600)  # GDELT's real limit for long ranges is far stricter than 5 s
        try:
            r = requests.get(url, headers={"User-Agent": "curl/8.4.0"}, timeout=120)
        except requests.RequestException as e:
            print(f"  network error {e}; retrying", flush=True)
            continue
        if r.status_code == 200 and "Please limit" not in r.text[:200]:
            return r.content.decode("utf-8-sig")
        print(f"  rate limited (attempt {attempt + 1}); backing off", flush=True)
    raise RuntimeError(f"gave up on {query} {mode}")


def parse(text, mode):
    df = pd.read_csv(StringIO(text))
    df.columns = [c.strip() for c in df.columns]
    if mode == "timelinevolraw":
        # two series per day: matching articles and total monitored articles
        wide = df.pivot_table(index="Date", columns="Series", values="Value").reset_index()
        wide.columns = ["date", "articles", "total_monitored"]
        return wide
    return df.rename(columns={"Date": "date", "Value": "tone"})[["date", "tone"]]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    if "--cooldown" in sys.argv:
        sys.argv.remove("--cooldown")
        time.sleep(600)  # let a previous rate-limit lockout expire
    teams = sys.argv[1:] or list(TEAMS)
    for name, mode in SERIES.items():  # all teams' tone first, then volume
        for abbr in teams:
            path = OUT / f"{abbr}_{name}.csv"
            if path.exists():
                continue
            df = parse(fetch(TEAMS[abbr]["query"], mode), mode)
            df.to_csv(path, index=False)
            print(f"{abbr} {name}: {len(df)} days", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
