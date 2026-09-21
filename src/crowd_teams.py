"""Wisdom of the crowd, team level: can collective attention pick the champion,
the standings and playoff series winners?

Crowds (each measured over a window BEFORE the prediction date, never after):
  media_attn   share of all NBA-team news articles about the team      (GDELT)
  media_tone   average tone of those articles                          (GDELT)
  fan_attn     share of all NBA-team Wikipedia pageviews                (Wikipedia)
  crowd_all    the "jelly bean" aggregate: average of the three ranks
Baselines (what the numbers alone say at the same moment):
  preseason    last season's win %
  in-season    point differential per game so far

Checkpoints each season: preseason (day before opening night), 25/50/75% of the
regular season, and the day before the playoffs.
Targets: final regular-season win % (standings), champion, playoff series winners.
Writes results/crowd_teams_*.csv and results/crowd_teams_log.txt
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import spearmanr

from teams import TEAMS

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
RES = ROOT / "results"
CROWDS = ["media_attn", "media_tone", "fan_attn", "crowd_all",
          "media_buzz", "fan_buzz", "crowd_buzz"]
WINDOW = 28  # days of attention before each checkpoint

log_lines = []


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    log_lines.append(s)


# ---------------------------------------------------------------- data
def load():
    games = pd.read_csv(RAW / "games.csv", parse_dates=["date"])
    teams = sorted(TEAMS)  # the 30 franchises (drops All-Star exhibition teams)
    games = games[games.home.isin(teams) & games.away.isin(teams)]
    news = pd.read_csv(RAW / "gdelt_bq.csv", parse_dates=["day"]).rename(columns={"day": "date"})
    wiki = pd.concat([pd.read_csv(RAW / "wiki" / f"{t}.csv", parse_dates=["date"]).assign(team=t)
                      for t in teams if (RAW / "wiki" / f"{t}.csv").exists()])
    return games, news, wiki, teams


def team_games(games):
    h = games.assign(team=games.home, pts=games.home_pts, opp_pts=games.away_pts)
    a = games.assign(team=games.away, pts=games.away_pts, opp_pts=games.home_pts)
    tg = pd.concat([h, a])
    tg["margin"] = tg.pts - tg.opp_pts
    tg["win"] = (tg.margin > 0).astype(int)
    return tg


def crowd_snapshot(news, wiki, date, days=WINDOW):
    """Each crowd's view of every team over the `days` before `date`."""
    lo = date - pd.Timedelta(days=days)
    n = news[(news.date >= lo) & (news.date < date)]
    w = wiki[(wiki.date >= lo) & (wiki.date < date)]
    snap = pd.DataFrame({
        "media_attn": n.groupby("team").articles.sum(),
        "media_tone": n.assign(tx=n.tone_mean * n.articles).groupby("team").tx.sum()
                      / n.groupby("team").articles.sum(),
        "fan_attn": w.groupby("team").views.sum(),
    })
    snap["media_attn"] /= snap.media_attn.sum()
    snap["fan_attn"] /= snap.fan_attn.sum()
    # buzz = attention share now vs the team's own share over the previous year
    # (removes the permanent big-market / famous-franchise effect)
    base_lo = date - pd.Timedelta(days=365)
    nb = news[(news.date >= base_lo) & (news.date < lo)].groupby("team").articles.sum()
    wb = wiki[(wiki.date >= base_lo) & (wiki.date < lo)].groupby("team").views.sum()
    snap["media_buzz"] = np.log(snap.media_attn / (nb / nb.sum()))
    snap["fan_buzz"] = np.log(snap.fan_attn / (wb / wb.sum()))
    # jelly bean: average the three crowds' rankings (1 = crowd's favourite)
    ranks = snap[["media_attn", "media_tone", "fan_attn"]].rank(ascending=False)
    snap["crowd_all"] = -ranks.mean(axis=1)  # higher = more favoured, like the others
    ranks_b = snap[["media_buzz", "media_tone", "fan_buzz"]].rank(ascending=False)
    snap["crowd_buzz"] = -ranks_b.mean(axis=1)
    return snap


# ---------------------------------------------------------------- does the crowd add to the stats?
SIGNALS = ["media_buzz", "fan_buzz", "media_attn", "fan_attn", "media_tone"]


def beyond_stats(games, news, wiki, rs):
    """Regress outcomes on the stats baseline PLUS one crowd signal at a time."""
    panel, series = [], []
    for season in sorted(rs.season.unique()):
        reg = rs[rs.season == season]
        start, end = reg.date.min(), reg.date.max()
        for frac in (0.25, 0.5, 0.75):
            d = start + (end - start) * frac
            snap = crowd_snapshot(news, wiki, d)
            so_far, rest = reg[reg.date < d], reg[reg.date >= d]
            panel.append(snap.assign(pdiff=so_far.groupby("team").margin.mean(),
                                     ros=rest.groupby("team").win.mean(),
                                     checkpoint=frac, season=season).reset_index(names="team"))
        post = games[(games.season == season) & (games.season_type == "post-season")].copy()
        if post.empty:
            continue
        post["pair"] = post.apply(lambda r: tuple(sorted((r.home, r.away))), axis=1)
        pdiff = reg.groupby("team").margin.mean()
        for (a, b), s in post.groupby("pair"):
            a_wins = ((s.home == a) & (s.home_pts > s.away_pts)).sum() + ((s.away == a) & (s.away_pts > s.home_pts)).sum()
            snap = crowd_snapshot(news, wiki, s.date.min(), days=14)
            series.append({"season": season, "a_wins": int(a_wins > len(s) - a_wins),
                           "d_pdiff": pdiff[a] - pdiff[b],
                           **{f"d_{c}": snap[c][a] - snap[c][b] for c in SIGNALS}})
    P, S = pd.concat(panel), pd.DataFrame(series)
    rows = []
    log("\n=== BEYOND STATS: rest-of-season win % ~ point diff so far + crowd signal")
    log("    (11 seasons x 3 checkpoints x 30 teams; standard errors clustered by team)")
    for c in SIGNALS:
        d = P.dropna(subset=[c, "pdiff", "ros"])
        m = smf.ols(f"ros ~ pdiff + {c} + C(checkpoint)", data=d).fit(cov_type="cluster", cov_kwds={"groups": d.team})
        rows.append({"target": "rest_of_season_win_pct", "signal": c, "coef": m.params[c], "p": m.pvalues[c], "n": int(m.nobs)})
        log(f"  {c:11s} coef {m.params[c]:+.4f}  p = {m.pvalues[c]:.3f}")
    base = smf.logit("a_wins ~ d_pdiff", data=S).fit(disp=0)
    log(f"\n=== BEYOND STATS: playoff series winner ~ point-diff gap + crowd gap (logit, n={len(S)})")
    log(f"  stats only: pseudo-R2 {base.prsquared:.3f}")
    for c in SIGNALS:
        m = smf.logit(f"a_wins ~ d_pdiff + d_{c}", data=S.dropna()).fit(disp=0)
        rows.append({"target": "playoff_series", "signal": c, "coef": m.params[f"d_{c}"],
                     "p": m.pvalues[f"d_{c}"], "n": int(m.nobs), "pseudo_r2": m.prsquared})
        log(f"  {c:11s} coef {m.params[f'd_{c}']:+.3f}  p = {m.pvalues[f'd_{c}']:.3f}  pseudo-R2 {m.prsquared:.3f}")
    pd.DataFrame(rows).to_csv(RES / "crowd_teams_beyond_stats.csv", index=False)


# ---------------------------------------------------------------- analysis
def main():
    RES.mkdir(exist_ok=True)
    games, news, wiki, teams = load()
    tg = team_games(games)
    rs = tg[tg.season_type == "regular-season"]
    seasons = sorted(s for s in rs.season.unique() if news.date.min() < rs[rs.season == s].date.min())
    log(f"seasons {seasons[0]}-{seasons[-1]} ({len(seasons)}), teams {len(teams)}")

    standings_rows, champ_rows, series_rows = [], [], []
    for season in seasons:
        reg = rs[rs.season == season]
        final_wpct = reg.groupby("team").win.mean()
        prev = rs[rs.season == season - 1].groupby("team").win.mean()
        start, end = reg.date.min(), reg.date.max()
        post = tg[(tg.season == season) & (tg.season_type == "post-season")]
        champion = None
        if len(post):
            finals_teams = post[post.date == post.date.max()].team.unique()
            last = post[post.date >= post.date.max() - pd.Timedelta(days=20)]
            # champion = team with most wins in the last series
            champion = last[last.team.isin(finals_teams)].groupby("team").win.sum().idxmax()

        checkpoints = {"preseason": start}
        for frac in (0.25, 0.5, 0.75):
            checkpoints[f"{int(frac*100)}%"] = start + (end - start) * frac
        checkpoints["pre-playoffs"] = post.date.min() if len(post) else end

        for cp, date in checkpoints.items():
            snap = crowd_snapshot(news, wiki, date)
            played = reg[reg.date < date]
            if cp == "preseason":
                base = prev.reindex(snap.index)
                base_name = "last season win%"
            else:
                base = played.groupby("team").margin.mean().reindex(snap.index)
                base_name = "point diff so far"
            # target: final win % (for in-season checkpoints, rest-of-season win %)
            future = reg[reg.date >= date].groupby("team").win.mean() if cp != "preseason" else final_wpct
            for name, score in list({c: snap[c] for c in CROWDS}.items()) + [("stats_baseline", base)]:
                if cp == "pre-playoffs":
                    break  # regular season is over: no standings left to predict
                ok = score.notna() & future.reindex(score.index).notna()
                rho = spearmanr(score[ok], future.reindex(score.index)[ok]).statistic
                standings_rows.append({"season": season, "checkpoint": cp, "predictor": name, "spearman": rho})
            if champion:
                for name, score in list({c: snap[c] for c in CROWDS}.items()) + [("stats_baseline", base)]:
                    order = score.rank(ascending=False)
                    champ_rows.append({"season": season, "checkpoint": cp, "predictor": name,
                                       "champion": champion, "champion_rank": order.get(champion)})

        # playoff series: pairs of teams meeting in the post-season
        if len(post):
            post_g = games[(games.season == season) & (games.season_type == "post-season")].copy()
            post_g["pair"] = post_g.apply(lambda r: tuple(sorted((r.home, r.away))), axis=1)
            for pair, s in post_g.groupby("pair"):
                wins = {t: ((s.home == t) & (s.home_pts > s.away_pts)).sum()
                        + ((s.away == t) & (s.away_pts > s.home_pts)).sum() for t in pair}
                winner = max(wins, key=wins.get)
                snap = crowd_snapshot(news, wiki, s.date.min(), days=14)
                wp = reg.groupby("team").win.mean()
                row = {"season": season, "series": f"{pair[0]}-{pair[1]}", "winner": winner}
                for c in CROWDS:
                    row[c] = snap[c].get(winner, np.nan) > snap[c].get([t for t in pair if t != winner][0], np.nan)
                loser = [t for t in pair if t != winner][0]
                row["stats_baseline"] = wp[winner] > wp[loser]  # better regular-season record
                series_rows.append(row)

    st = pd.DataFrame(standings_rows)
    ch = pd.DataFrame(champ_rows)
    se = pd.DataFrame(series_rows)
    st.to_csv(RES / "crowd_teams_standings.csv", index=False)
    ch.to_csv(RES / "crowd_teams_champion.csv", index=False)
    se.to_csv(RES / "crowd_teams_series.csv", index=False)

    order = ["preseason", "25%", "50%", "75%", "pre-playoffs"]
    log("\n=== STANDINGS: Spearman correlation between predictor and final (or rest-of-season) win %")
    log("    averaged over seasons; 1 = perfect ranking, 0 = no relationship")
    t = st.pivot_table(index="predictor", columns="checkpoint", values="spearman", aggfunc="mean")[order[:-1]]
    log(t.round(2).to_string())
    log("\n=== CHAMPION: where the eventual champion sat in each predictor's ranking (1 = top pick)")
    c = ch.groupby(["predictor", "checkpoint"]).champion_rank.agg(
        median_rank="median", top1=lambda r: (r == 1).mean(), top3=lambda r: (r <= 3).mean()).unstack()
    for stat in ("top1", "top3", "median_rank"):
        log(f"-- {stat}")
        log(c[stat][order].round(2).to_string())
    log(f"\n=== PLAYOFF SERIES ({len(se)} series): share where the predictor favoured the winner")
    acc = se[CROWDS + ["stats_baseline"]].astype(float)
    n = len(acc)
    summary = pd.DataFrame({"accuracy": acc.mean(), "se": np.sqrt(acc.mean() * (1 - acc.mean()) / n)})
    log(summary.round(3).to_string())
    beyond_stats(games, news, wiki, rs)
    (RES / "crowd_teams_log.txt").write_text("\n".join(log_lines), encoding="utf8")


if __name__ == "__main__":
    main()
