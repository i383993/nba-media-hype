"""Download pre-game betting lines for every game in data/raw/games.csv from ESPN.

ESPN's odds feed lists one or more sportsbooks per game. For each game we keep
- the consensus (median across books) spread, total and moneylines
- opening and closing spread/moneyline when ESPN has them (recent seasons)

Resumable: already-fetched games are cached as JSON in data/raw/espn_odds/.
Output: data/raw/espn_odds.csv (spread is from the HOME team's side).
"""
import json
import time
from pathlib import Path
from statistics import median

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "raw" / "espn_odds"
URL = "https://sports.core.api.espn.com/v2/sports/basketball/leagues/nba/events/{id}/competitions/{id}/odds"


def fetch(session, gid):
    path = CACHE / f"{gid}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf8"))
    for attempt in range(4):
        try:
            r = session.get(URL.format(id=gid), timeout=30)
            if r.status_code == 404:
                data = {"items": []}
                break
            r.raise_for_status()
            data = r.json()
            break
        except requests.RequestException:
            time.sleep(5 * (attempt + 1))
    else:
        return None
    path.write_text(json.dumps(data), encoding="utf8")
    time.sleep(0.25)
    return data


def num(x):
    try:
        x = float(x)
        return x if x != 0 else None
    except (TypeError, ValueError):
        return None


def summarize(gid, data):
    # drop in-game ("Live Odds") feeds: they are not pre-game lines
    books = [b for b in data.get("items", []) if "live" not in b["provider"]["name"].lower()]
    spreads = [num(b.get("spread")) for b in books]
    spreads = [s for s in spreads if s is not None]
    totals = [t for t in (num(b.get("overUnder")) for b in books) if t is not None]
    ml_h = [m for m in (num((b.get("homeTeamOdds") or {}).get("moneyLine")) for b in books) if m is not None]
    ml_a = [m for m in (num((b.get("awayTeamOdds") or {}).get("moneyLine")) for b in books) if m is not None]
    row = {
        "espn_id": gid,
        "n_books": len(books),
        "books": "|".join(sorted({b["provider"]["name"] for b in books})),
        "spread_home": median(spreads) if spreads else None,
        "spread_sd": pd.Series(spreads).std() if len(spreads) > 1 else None,
        "total": median(totals) if totals else None,
        "ml_home": median(ml_h) if ml_h else None,
        "ml_away": median(ml_a) if ml_a else None,
    }
    consensus = [b for b in books if b["provider"]["name"].lower() == "consensus"]
    if consensus:
        row["spread_consensus"] = num(consensus[0].get("spread"))
    # open / close lines (present for recent seasons, usually DraftKings)
    for b in books:
        h = b.get("homeTeamOdds") or {}
        if "open" in h and "close" in h:
            for when in ("open", "close"):
                pts = ((h.get(when) or {}).get("pointSpread") or {}).get("american")
                ml = ((h.get(when) or {}).get("moneyLine") or {}).get("american")
                row[f"spread_home_{when}"] = num(str(pts).replace("+", "")) if pts not in (None, "EVEN") else None
                row[f"ml_home_{when}"] = num(str(ml).replace("+", "")) if ml not in (None, "EVEN") else None
            row["oc_book"] = b["provider"]["name"]
            break
    return row


def main(seasons=None):
    CACHE.mkdir(parents=True, exist_ok=True)
    games = pd.read_csv(ROOT / "data" / "raw" / "games.csv")
    if seasons:  # e.g. to download older seasons in a parallel process
        games = games[games.season.isin(seasons)]
    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0 (academic research)"
    rows = []
    for i, gid in enumerate(games.espn_id):  # cached games are read from disk, so reruns are fast
        data = fetch(session, gid)
        if data is not None:
            rows.append(summarize(gid, data))
        if i % 500 == 0:
            print(f"{i}/{len(games)}", flush=True)
    out = pd.DataFrame(rows)
    if seasons:
        print("fetched", len(out), "games for", seasons, "(run without arguments to write the CSV)")
        return
    out.to_csv(ROOT / "data" / "raw" / "espn_odds.csv", index=False)
    print("saved", len(out), "with spread:", out.spread_home.notna().sum(),
          "with open/close:", out.get("spread_home_close", pd.Series(dtype=float)).notna().sum())


if __name__ == "__main__":
    import sys
    main([int(x) for x in sys.argv[1:]] or None)
