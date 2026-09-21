"""Pre-registered live test for the 2026-27 season.

Run once per game day BEFORE the first tip-off, then commit the output file so
GitHub's commit time proves the prediction came before the result:

    python fetch_games.py 2027      # update results through yesterday (for team form)
    python predict_live.py          # writes predictions/<today>.csv
    git add predictions && git commit -m "picks <today>" && git push

The rule is frozen from results/hype_model.json (fitted on 2018-19..2024-25):
for each game, compute each team's public-attention hype (Wikipedia pageviews
not explained by recent performance); if the home-minus-away hype gap is at
least the training threshold, pick the LESS hyped team against the spread.
`score_live.py` later grades these picks.
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from build_dataset import team_view, load_games
from fetch_espn_odds import URL as ODDS, summarize
from fetch_games import FIX
from fetch_wiki import HEADERS, article
from teams import TEAMS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "predictions"
SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
WIKI = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/"
        "all-access/user/{article}/daily/{start}/{end}")
MEASURE = "hype_wiki"


def todays_games(day):
    r = requests.get(SCOREBOARD, params={"dates": f"{day:%Y%m%d}"}, timeout=30)
    r.raise_for_status()
    rows = []
    for e in r.json().get("events", []):
        comp = e["competitions"][0]
        side = {t["homeAway"]: FIX.get(t["team"]["abbreviation"], t["team"]["abbreviation"])
                for t in comp["competitors"]}
        odds = (comp.get("odds") or [{}])[0]
        rows.append({"espn_id": int(e["id"]), "tipoff_utc": e["date"], "home": side["home"],
                     "away": side["away"], "spread_home": odds.get("spread"),
                     "line_source": (odds.get("provider") or {}).get("name")})
    return pd.DataFrame(rows)


def wiki_7d(team, day):
    """Mean log pageviews over the 7 days before `day` (same definition as training)."""
    start, end = day - pd.Timedelta(days=7), day - pd.Timedelta(days=1)
    url = WIKI.format(article=article(TEAMS[team]["query"]), start=f"{start:%Y%m%d}", end=f"{end:%Y%m%d}")
    for attempt in range(5):
        r = requests.get(url, headers=HEADERS, timeout=30)
        if r.status_code != 429:
            break
        time.sleep(20 * (attempt + 1))  # Wikimedia rate limit
    r.raise_for_status()
    time.sleep(2)
    return float(np.log1p(pd.Series([i["views"] for i in r.json()["items"]])).mean())


def current_form(day):
    """Each team's form entering `day`, from games already played this season."""
    g = load_games()
    g = g[pd.to_datetime(g.date) < day]
    tg = team_view(g.assign(spread_home=np.nan))
    season = tg.season.max()
    last = tg[tg.season == season].sort_values("date").groupby("team").tail(1)
    # team_view gives form ENTERING each game; roll forward to include that last game
    out = {}
    for _, r in last.iterrows():
        hist = tg[(tg.team == r.team) & (tg.season == season)].margin
        wins = (hist > 0).astype(int)
        streak = 0
        for w in wins[::-1]:
            if streak == 0 or (w == 1) == (streak > 0):
                streak += 1 if w == 1 else -1
            else:
                break
        out[r.team] = {"form_margin_10": hist.tail(10).mean() if len(hist) >= 3 else np.nan,
                       "form_margin_season": hist.mean() if len(hist) >= 3 else np.nan,
                       "streak": streak, "last_margin": hist.iloc[-1]}
    return out


def main(day=None, dry_run=False):
    model = json.loads((ROOT / "results" / "hype_model.json").read_text())
    m, threshold = model[MEASURE], model["fade_threshold"][f"d_{MEASURE}"]
    day = day or pd.Timestamp.now(tz="US/Eastern").normalize().tz_localize(None)
    games = todays_games(day)
    if games.empty:
        print("no games today")
        return
    missing = games.spread_home.isna()
    if missing.any():  # scoreboard sometimes omits odds; fall back to the odds feed
        for i in games.index[missing]:
            r = requests.get(ODDS.format(id=games.at[i, "espn_id"]), timeout=30)
            if r.ok:
                games.at[i, "spread_home"] = summarize(games.at[i, "espn_id"], r.json())["spread_home"]
                games.at[i, "line_source"] = "espn consensus"
    form = current_form(day)

    def hype(team):
        f = form.get(team)
        if f is None or any(pd.isna(v) for v in f.values()):
            return np.nan  # too early in the season for a form estimate
        expected = m["intercept"] + sum(m["coef"][c] * f[c] for c in m["coef"])
        return wiki_7d(team, day) - expected

    games["hype_home"] = games.home.map(hype)
    games["hype_away"] = games.away.map(hype)
    games["d_hype"] = games.hype_home - games.hype_away
    games["pick"] = np.where(games.d_hype.abs() >= threshold,
                             np.where(games.d_hype < 0, games.home, games.away), "")
    games["pick_spread"] = np.where(games.pick == games.home, games.spread_home,
                                    np.where(games.pick == games.away, -games.spread_home.astype(float), np.nan))
    games["threshold"] = threshold
    games["generated_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(games[["home", "away", "spread_home", "d_hype", "pick"]].to_string(index=False))
    if dry_run:
        return
    OUT.mkdir(exist_ok=True)
    path = OUT / f"{day:%Y-%m-%d}.csv"
    games.to_csv(path, index=False)
    print("saved", path)


if __name__ == "__main__":
    import sys
    # testing: python predict_live.py 2026-03-10  (prints picks for a past day, saves nothing)
    if len(sys.argv) > 1:
        main(pd.Timestamp(sys.argv[1]), dry_run=True)
    else:
        main()
