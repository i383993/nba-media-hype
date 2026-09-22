"""Quick check (not a full analysis): does the most-covered MVP candidate,
by news attention in the last 28 days of the regular season, match the
actual MVP? One-sentence illustration for the abstract's introduction --
the deeper, statistically validated finding is the media_buzz result in
crowd_teams.py / results/crowd_teams_beyond_stats.csv.

Restricted to that season's actual MVP-ballot candidates (a fair contest:
"among the players who got real MVP consideration, would raw attention
have picked the winner?"), using GDELT news coverage only (player-level
Wikipedia data wasn't fully downloaded in time for this check).
Output: results/mvp_naive_pick.csv
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW, RES = ROOT / "data" / "raw", ROOT / "results"


def main():
    awards = pd.read_csv(RAW / "awards.csv")
    mvp = awards[awards.award == "MVP"].copy()
    mvp["name_key_lc"] = mvp.name_key.str.lower()
    winners = mvp[mvp["rank"] == 1].set_index("season").name_key_lc
    candidates = mvp.groupby("season").name_key_lc.apply(set)

    people = pd.read_csv(RAW / "gdelt_people.csv", parse_dates=["day"]).rename(columns={"day": "date"})
    reg = pd.read_csv(RAW / "games.csv", parse_dates=["date"])
    reg = reg[reg.season_type == "regular-season"]

    rows = []
    for season in sorted(set(winners.index) & set(reg.season.unique())):
        s = reg[reg.season == season]
        end = s.date.max()
        lo = end - pd.Timedelta(days=28)
        win = people[(people.date >= lo) & (people.date < end) & people.name_key.isin(candidates[season])]
        if win.empty:
            continue
        attn = win.groupby("name_key").articles.sum().sort_values(ascending=False)
        rows.append({"season": season, "crowd_pick": attn.index[0], "actual_mvp": winners[season],
                     "match": attn.index[0] == winners[season], "n_candidates_covered": len(attn)})

    df = pd.DataFrame(rows)
    df.to_csv(RES / "mvp_naive_pick.csv", index=False)
    print(df.to_string(index=False))
    print(f"\ncrowd's most-covered candidate matched the actual MVP in "
          f"{df.match.sum()} of {len(df)} seasons ({df.match.mean():.1%})")
    print(f"crowd's pick was LeBron James in {(df.crowd_pick == 'lebron james').sum()} of {len(df)} seasons")


if __name__ == "__main__":
    main()
