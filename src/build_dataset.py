"""Join odds + game results + media coverage into one team-game table.

Every game appears twice (once from each team's side). All features use only
information available BEFORE tip-off (media up to the previous day, results of
earlier games), so nothing leaks from the game being predicted.

Output: data/team_games.csv
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

from teams import TEAMS, YAHOO_TO_ABBR

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"


# ---------------------------------------------------------------- odds
def load_espn_odds():
    """Consensus + open/close lines for every game (2018-19 onward)."""
    o = pd.read_csv(RAW / "espn_odds.csv")
    # closing line where ESPN has it, otherwise the consensus across books
    close = o.get("spread_home_close")
    o["spread_close"] = close.fillna(o.spread_home) if close is not None else o.spread_home
    o["line_move"] = o.spread_close - o.get("spread_home_open", np.nan)  # <0: moved toward home
    return o


def load_yahoo():
    """Yahoo lines + public betting splits (2021-22 to 2024-25 only)."""
    files = sorted(glob.glob(str(RAW / "odds_yahoo" / "*.csv")))
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df = df.drop_duplicates("game_id")
    df["date"] = pd.to_datetime(df.game_date.str[:10]).dt.date
    df["home"] = df.home_team.map(YAHOO_TO_ABBR)
    df["away"] = df.away_team.map(YAHOO_TO_ABBR)
    df = df.dropna(subset=["home", "away", "spread_home_points"])
    keep = {
        "game_id": "yahoo_id", "date": "date", "home": "home", "away": "away",
        "spread_home_points": "yahoo_spread_home",
        "spread_home_wager_percentage": "pub_bets_home",  # % of tickets on home spread
        "spread_home_stake_percentage": "pub_money_home",  # % of dollars on home spread
    }
    return df[list(keep)].rename(columns=keep)


def implied_prob(ml):
    ml = ml.astype(float)
    return np.where(ml < 0, -ml / (-ml + 100), 100 / (ml + 100))


# ---------------------------------------------------------------- media
def load_media():
    frames = []
    for abbr in TEAMS:
        tone_p, vol_p = RAW / "gdelt" / f"{abbr}_tone.csv", RAW / "gdelt" / f"{abbr}_volraw.csv"
        if not tone_p.exists():
            continue
        m = pd.read_csv(tone_p)
        if vol_p.exists():
            m = m.merge(pd.read_csv(vol_p), on="date", how="outer")
        else:  # volume not downloaded yet: equal-weight days, no attention measure
            m["articles"] = np.where(m.tone.notna(), 1.0, 0.0)
            m["total_monitored"] = np.nan
        m["team"] = abbr
        frames.append(m)
    if not frames:
        return None
    m = pd.concat(frames, ignore_index=True)
    m["date"] = pd.to_datetime(m.date)
    m = m.sort_values(["team", "date"])
    # attention = team's share of all monitored news that day (per 100k articles)
    m["attention"] = 1e5 * m.articles / m.total_monitored
    feats = []
    for team, g in m.groupby("team"):
        g = g.set_index("date").asfreq("D")
        g["team"] = team
        w = g.articles.fillna(0)
        tone_x_w = (g.tone * w).fillna(0)
        for k in (3, 7, 28):
            g[f"tone_{k}d"] = tone_x_w.rolling(k, min_periods=1).sum() / w.rolling(k, min_periods=1).sum()
            g[f"attn_{k}d"] = g.attention.fillna(0).rolling(k, min_periods=1).mean()
        # abnormal attention: last week vs the previous month
        g["attn_surge"] = np.log1p(g.attn_7d) - np.log1p(g.attn_28d)
        g["tone_shift"] = g.tone_7d - g.tone_28d
        # shift by one day: a game on day D only sees coverage up to D-1
        cols = [c for c in g.columns if c.startswith(("tone_", "attn_"))]
        g[cols] = g[cols].shift(1)
        feats.append(g.reset_index()[["date", "team"] + cols])
    out = pd.concat(feats, ignore_index=True)
    out["date"] = out.date.dt.date
    return out


def load_wiki():
    """Public attention: daily Wikipedia pageviews of the team's article."""
    frames = []
    for abbr in TEAMS:
        p = RAW / "wiki" / f"{abbr}.csv"
        if not p.exists():
            continue
        w = pd.read_csv(p, parse_dates=["date"]).set_index("date").asfreq("D")
        lv = np.log1p(w.views.ffill())
        f = pd.DataFrame({
            "wiki_7d": lv.rolling(7, min_periods=1).mean(),
            "wiki_28d": lv.rolling(28, min_periods=1).mean(),
        })
        f["wiki_surge"] = f.wiki_7d - f.wiki_28d
        f = f.shift(1)  # game on day D sees pageviews through D-1
        f["team"] = abbr
        frames.append(f.reset_index())
    if not frames:
        return None
    out = pd.concat(frames, ignore_index=True)
    out["date"] = out.date.dt.date
    return out


# ---------------------------------------------------------------- results + form
def load_games():
    g = pd.read_csv(RAW / "games.csv")
    g = g[g.home.isin(TEAMS) & g.away.isin(TEAMS)]  # drops All-Star games
    g["date"] = pd.to_datetime(g.date).dt.date
    return g


def team_view(games):
    """Two rows per game with rolling pre-game form for the team."""
    h = games.assign(team=games.home, opp=games.away, is_home=1,
                     pts=games.home_pts, opp_pts=games.away_pts)
    a = games.assign(team=games.away, opp=games.home, is_home=0,
                     pts=games.away_pts, opp_pts=games.home_pts)
    tg = pd.concat([h, a], ignore_index=True).sort_values(["team", "date"])
    tg["margin"] = tg.pts - tg.opp_pts
    tg["win"] = (tg.margin > 0).astype(int)
    grp = tg.groupby(["team", "season"])
    # form uses games strictly before this one
    tg["form_margin_10"] = grp.margin.transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    tg["form_margin_season"] = grp.margin.transform(lambda s: s.shift(1).expanding(min_periods=3).mean())
    tg["form_win_10"] = grp.win.transform(lambda s: s.shift(1).rolling(10, min_periods=3).mean())
    tg["last_margin"] = grp.margin.shift(1)
    # current streak (+n wins / -n losses) entering the game
    def streak(s):
        out, cur = [], 0
        for w in s.shift(1):
            out.append(cur)
            if pd.isna(w):
                continue
            cur = cur + 1 if (w == 1 and cur >= 0) else (cur - 1 if (w == 0 and cur <= 0) else (1 if w == 1 else -1))
        return pd.Series(out, index=s.index)
    tg["streak"] = grp.win.transform(streak)
    tg["rest_days"] = grp.date.transform(lambda s: pd.to_datetime(s).diff().dt.days.clip(upper=7))
    tg["game_no"] = grp.cumcount() + 1
    return tg


# ---------------------------------------------------------------- build
def main():
    games = load_games()
    g = games.merge(load_espn_odds(), on="espn_id", how="left")
    g = g.merge(load_yahoo(), on=["date", "home", "away"], how="left")
    g["spread_home"] = g.spread_close  # e.g. -5.5 = home favored by 5.5
    both = g.yahoo_spread_home.notna() & g.spread_home.notna()
    print(f"games {len(games)}; with ESPN line {g.spread_home.notna().sum()}; "
          f"with public-betting splits {g.pub_bets_home.notna().sum()}; "
          f"ESPN vs Yahoo spread within 1 pt: {(abs(g.spread_home - g.yahoo_spread_home)[both] <= 1).mean():.3f}")
    # games without a line stay in: they still count toward each team's recent form

    tg = team_view(g)
    # betting line from the team's side
    home = tg.is_home == 1
    tg["spread"] = np.where(home, tg.spread_home, -tg.spread_home)   # negative = team favored
    tg["exp_margin"] = -tg.spread
    tg["ats_margin"] = tg.margin + tg.spread                            # >0 means team covered
    tg["cover"] = np.where(tg.ats_margin > 0, 1.0, 0.0)
    tg.loc[tg.ats_margin.isna() | (tg.ats_margin == 0), "cover"] = np.nan  # no line, or push
    p_home = implied_prob(tg.ml_home)
    p_away = implied_prob(tg.ml_away)
    tg["mkt_win_prob"] = np.where(home, p_home, p_away) / (p_home + p_away)  # remove bookmaker margin
    tg["pub_bets"] = np.where(home, tg.pub_bets_home, 100 - tg.pub_bets_home)
    tg["pub_money"] = np.where(home, tg.pub_money_home, 100 - tg.pub_money_home)

    for name, media in [("GDELT news", load_media()), ("Wikipedia", load_wiki())]:
        if media is None:
            continue
        tg = tg.merge(media, on=["date", "team"], how="left")
        opp = media.add_prefix("opp_").rename(columns={"opp_date": "date", "opp_team": "opp"})
        tg = tg.merge(opp, on=["date", "opp"], how="left")
        col = [c for c in media.columns if c not in ("date", "team")][0]
        print(f"{name} coverage for {tg[col].notna().mean():.3f} of team-games")

    tg = tg.sort_values(["date", "espn_id", "is_home"])
    tg.to_csv(ROOT / "data" / "team_games.csv", index=False)
    print("saved", len(tg), "team-games;", tg.season.value_counts().sort_index().to_dict())


if __name__ == "__main__":
    main()
