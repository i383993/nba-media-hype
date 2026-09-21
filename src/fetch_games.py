"""Download NBA game results from ESPN's public scoreboard feed.

(stats.nba.com via nba_api times out from many networks, so we use ESPN.)
One request per day (ESPN rejects date ranges). Output: data/raw/games.csv, one row per game,
with the game date in US/Eastern so it lines up with the odds data.
"""
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
# ESPN abbreviations that differ from nba_api / teams.py
FIX = {"NY": "NYK", "GS": "GSW", "SA": "SAS", "NO": "NOP", "UTAH": "UTA", "WSH": "WAS", "PHX": "PHX"}


SEASON_DATES = {  # regular season start -> end of Finals (2019-20 and 2020-21 were COVID-shifted)
    2016: ("2015-10-25", "2016-06-22"), 2017: ("2016-10-22", "2017-06-15"),
    2018: ("2017-10-15", "2018-06-10"), 2019: ("2018-10-15", "2019-06-15"), 2020: ("2019-10-20", "2020-10-12"),
    2021: ("2020-12-20", "2021-07-22"), 2022: ("2021-10-15", "2022-06-20"),
    2023: ("2022-10-15", "2023-06-20"), 2024: ("2023-10-20", "2024-06-20"),
    2025: ("2024-10-20", "2025-06-25"), 2026: ("2025-10-18", "2026-06-25"),
    2027: ("2026-10-15", "2027-06-25"),  # live season; future days return no games
}


def days(seasons):
    for season in seasons:
        start, end = SEASON_DATES[season]
        end = min(pd.Timestamp(end), pd.Timestamp.today().normalize() - pd.Timedelta(days=1))
        yield from pd.date_range(start, end, freq="D")


def main(seasons):
    rows = []
    session = requests.Session()
    for day in days(seasons):
        for attempt in range(3):
            try:
                r = session.get(URL, params={"dates": f"{day:%Y%m%d}"}, timeout=30)
                r.raise_for_status()
                break
            except requests.RequestException:
                time.sleep(5)
        else:
            raise RuntimeError(f"failed on {day:%Y-%m-%d}")
        for e in r.json().get("events", []):
            comp = e["competitions"][0]
            if not comp["status"]["type"]["completed"]:
                continue
            side = {t["homeAway"]: t for t in comp["competitors"]}
            abbr = lambda t: FIX.get(t["team"]["abbreviation"], t["team"]["abbreviation"])
            rows.append({
                "espn_id": int(e["id"]),
                "tipoff_utc": e["date"],
                "season": e["season"]["year"],          # 2025 = 2024-25 season
                "season_type": e["season"]["slug"],     # regular-season / post-season / play-in
                "home": abbr(side["home"]),
                "away": abbr(side["away"]),
                "home_pts": int(side["home"]["score"]),
                "away_pts": int(side["away"]["score"]),
            })
        if day.day == 1:
            print(f"{day:%Y-%m}: total {len(rows)}", flush=True)
        time.sleep(0.3)
    df = pd.DataFrame(rows).drop_duplicates("espn_id")
    df["date"] = (pd.to_datetime(df.tipoff_utc).dt.tz_convert("US/Eastern").dt.date)
    df = df[df.season_type != "preseason"]
    out = ROOT / "data" / "raw" / "games.csv"
    if out.exists():  # merge with seasons fetched earlier
        df = pd.concat([pd.read_csv(out), df]).drop_duplicates("espn_id", keep="last")
    df.to_csv(out, index=False)
    print("saved", len(df), df.season.value_counts().sort_index().to_dict())


if __name__ == "__main__":
    import sys
    main([int(x) for x in sys.argv[1:]] or [s for s in SEASON_DATES if s < 2027])
