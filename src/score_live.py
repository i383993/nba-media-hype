"""Grade the pre-registered live picks in predictions/ against final scores.

    python fetch_games.py 2027 && python score_live.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def main():
    files = sorted((ROOT / "predictions").glob("*.csv"))
    if not files:
        print("no predictions yet")
        return
    p = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    p = p[p.pick.notna() & (p.pick != "")]
    games = pd.read_csv(ROOT / "data" / "raw" / "games.csv")[["espn_id", "home_pts", "away_pts"]]
    p = p.merge(games, on="espn_id", how="left")
    done = p.dropna(subset=["home_pts"]).copy()
    margin = np.where(done.pick == done.home, done.home_pts - done.away_pts, done.away_pts - done.home_pts)
    done["ats"] = margin + done.pick_spread
    graded = done[done.ats != 0]
    wins = (graded.ats > 0).sum()
    n = len(graded)
    print(f"picks made {len(p)}, graded {n}, pushes {len(done) - n}, pending {len(p) - len(done)}")
    if n:
        rate = wins / n
        se = np.sqrt(rate * (1 - rate) / n)
        print(f"record {wins}-{n - wins}  win rate {rate:.3f} ± {1.96 * se:.3f}  "
              f"ROI at -110 {rate * 100 / 110 - (1 - rate):+.3f}  (break-even 0.524)")
    done.to_csv(ROOT / "results" / "live_scorecard.csv", index=False)


if __name__ == "__main__":
    main()
