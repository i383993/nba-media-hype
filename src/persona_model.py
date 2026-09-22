"""Mixture-of-experts model of collective bias: named "personas," each a proxy for
one well-documented human cognitive bias, combined two ways -- a naive unweighted
average (the jelly-bean test: do independent biases cancel out?) and a learned
linear combiner fit on training seasons and evaluated out of sample on a holdout
season (the actual "neural network" step: hand-built features, learned weights).

Personas (each a team z-score at a checkpoint, built only from data strictly
before that checkpoint -- no leakage):
  recency      last-10-game point differential minus season-long point differential
               (recency / hot-hand bias: overweighting what just happened)
  narrative    media tone left over after removing what current performance
               explains (availability bias: storylines that outrun the facts)
  prestige     team's trailing 3-year share of all news + Wikipedia attention
               (halo effect: a fixed "fame" prior, independent of this season)
  bandwagon    growth in a team's attention share since the previous checkpoint
               (herding: chasing whoever is already trending)
  anchoring    how closely this checkpoint's crowd ranking still matches the
               preseason crowd ranking (sticking with the initial take)
  star_power   attention on the team's PRIOR-season award-ballot players only
               (attribution to individual stars rather than the team; built from
               last season's award list, so it cannot leak this season's results)
  polarization how much news outlets DISAGREE in tone about the team right now
               (the anti-Surowiecki signal: independence, or its absence, among
               the journalists forming the "media crowd")

Note: an earlier version defined a `negativity` persona as tone_neg minus tone_pos.
It was dropped -- GDELT's tone score is computed as roughly (positive - negative),
so that persona was mechanically ~-1x the `narrative` persona (r=-0.98 between them,
confirmed in results/persona_log.txt), not an independent bias. `polarization`
(tone_sd, dispersion across outlets rather than average tone) replaces it.

Targets and checkpoints match crowd_teams.py, so results are directly comparable:
rest-of-season win %, champion rank, playoff series winner. HOLDOUT season is
withheld from fitting the learned combiner.
Writes results/persona_*.csv and results/persona_log.txt
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import spearmanr

from crowd_teams import RAW, RES, WINDOW, crowd_snapshot, load, team_games
from teams import TEAMS, YAHOO_TO_ABBR

HOLDOUT = 2026
PERSONAS = ["recency", "narrative", "prestige", "bandwagon", "anchoring", "star_power", "polarization"]
log_lines = []

# awards.csv team names come from three different PDF layouts: 2-4 letter codes
# ("DEN"), Yahoo-style city names ("Denver"), and a couple of one-off Lakers labels.
TEAM_ALIASES = {**YAHOO_TO_ABBR, "L.A. Lakers": "LAL", "Los Angeles Lakers": "LAL",
                "Los Angeles": "LAL"}  # every bare "Los Angeles" row in this dataset is a Laker


def normalize_team(t):
    if t in TEAMS:
        return t
    return TEAM_ALIASES.get(t)


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    log_lines.append(s)


# ---------------------------------------------------------------- extra inputs
def load_awards():
    a = pd.read_csv(RAW / "awards.csv")
    a = a.dropna(subset=["team"]).copy()
    a["team"] = a.team.map(normalize_team)
    unmapped = a.team.isna().sum()
    if unmapped:
        log(f"[awards] {unmapped} award rows had an unrecognized team name and were dropped")
    return a.dropna(subset=["team"]).drop_duplicates(["season", "name_key", "team"])[["season", "name_key", "team"]]


def prior_stars(awards):
    """season -> team -> set of name_keys who got award votes in any EARLIER season."""
    out = {}
    for season in sorted(awards.season.unique()) + [awards.season.max() + 1]:
        prior = awards[awards.season < season]
        out[season] = prior.groupby("team").name_key.apply(set).to_dict()
    return out


def load_people():
    p = RAW / "gdelt_people.csv"
    if not p.exists():
        return None
    return pd.read_csv(p, parse_dates=["day"]).rename(columns={"day": "date"})


def person_attention(people, names, date, days=WINDOW):
    if people is None or not names:
        return np.nan
    lo = date - pd.Timedelta(days=days)
    # gdelt_people.csv's name_key is lowercase (fetch_gdelt_people_bq.py lowercased before querying)
    lower_names = {n.lower() for n in names}
    hit = people[(people.date >= lo) & (people.date < date) & people.name_key.isin(lower_names)]
    return hit.articles.sum() if len(hit) else np.nan


# ---------------------------------------------------------------- personas
def news_polarization(news, date, days=WINDOW):
    """Article-weighted average of the DAILY tone spread (tone_sd) across outlets --
    high = outlets disagree about the team right now; low = one uniform narrative."""
    lo = date - pd.Timedelta(days=days)
    n = news[(news.date >= lo) & (news.date < date)]
    w = n.groupby("team").articles.sum()
    return n.assign(x=n.tone_sd.fillna(0) * n.articles).groupby("team").x.sum() / w


def attention_share(news, wiki, date, days=WINDOW):
    """A single combined attention-share number, used for the anchoring persona."""
    lo = date - pd.Timedelta(days=days)
    n = news[(news.date >= lo) & (news.date < date)].groupby("team").articles.sum()
    w = wiki[(wiki.date >= lo) & (wiki.date < date)].groupby("team").views.sum()
    return n.rank(pct=True).add(w.rank(pct=True), fill_value=0) / 2


def build_panel(games, news, wiki, awards, people, rs):
    stars = prior_stars(awards)
    prestige_lo_days = 365 * 3
    rows = []
    prev_attn_share = {}  # season -> previous checkpoint's combined attention share, for bandwagon

    for season in sorted(rs.season.unique()):
        reg = rs[rs.season == season]
        start, end = reg.date.min(), reg.date.max()
        checkpoints = [("preseason", start), ("25%", start + (end - start) * .25),
                       ("50%", start + (end - start) * .5), ("75%", start + (end - start) * .75)]
        final_wpct = reg.groupby("team").win.mean()
        team_stars = stars.get(season, {})
        preseason_attn = attention_share(news, wiki, start)  # the "anchor": fixed for the whole season

        for cp, date in checkpoints:
            snap = crowd_snapshot(news, wiki, date)               # media_attn, media_tone, fan_attn, ...
            base_lo = date - pd.Timedelta(days=prestige_lo_days)
            long_news_share = news[(news.date >= base_lo) & (news.date < date)].groupby("team").articles.sum()
            long_news_share = long_news_share / long_news_share.sum()
            long_wiki_share = wiki[(wiki.date >= base_lo) & (wiki.date < date)].groupby("team").views.sum()
            long_wiki_share = long_wiki_share / long_wiki_share.sum()
            so_far = reg[reg.date < date].sort_values("date")
            pdiff_all = so_far.groupby("team").margin.mean()
            pdiff_10 = so_far.groupby("team").margin.apply(lambda s: s.tail(10).mean())
            ros = reg[reg.date >= date].groupby("team").win.mean() if cp != "preseason" else final_wpct
            attn_now = attention_share(news, wiki, date)

            df = pd.DataFrame(index=sorted(TEAMS.keys()))
            df["recency"] = pdiff_10 - pdiff_all
            df["narrative"] = snap.media_tone  # residualized against performance after pooling (see caller)
            df["prestige"] = np.log1p(1e6 * long_news_share) + np.log1p(1e6 * long_wiki_share)
            df["bandwagon"] = attn_now - prev_attn_share.get(season, pd.Series(dtype=float)).reindex(df.index)
            # anchoring: how far THIS checkpoint's attention has drifted from the preseason anchor
            # (near 0 = still anchored on the preseason take; the team's current rank hasn't moved)
            df["anchoring"] = -1 * (attn_now - preseason_attn).abs().reindex(df.index)
            df["star_power"] = [np.log1p(person_attention(people, team_stars.get(t, set()), date)) for t in df.index]
            df["polarization"] = news_polarization(news, date).reindex(df.index)
            df["season"], df["checkpoint"], df["team"] = season, cp, df.index
            df["pdiff"] = pdiff_all
            df["ros"] = ros.reindex(df.index)
            rows.append(df.reset_index(drop=True))
            prev_attn_share[season] = attn_now

    return pd.concat(rows, ignore_index=True)


def add_narrative_residual(panel):
    """narrative persona = media tone AFTER removing what point-differential explains."""
    train = panel[(panel.season < HOLDOUT)].dropna(subset=["narrative", "pdiff"])
    m = smf.ols("narrative ~ pdiff + C(checkpoint)", data=train).fit()
    pred = m.params["Intercept"] + m.params["pdiff"] * panel.pdiff
    for cp in panel.checkpoint.unique():
        pred = pred.where(panel.checkpoint != cp, pred + m.params.get(f"C(checkpoint)[T.{cp}]", 0))
    panel["narrative"] = panel.narrative - pred
    return panel, m.rsquared


def zscore(panel):
    z = panel.copy()
    for c in PERSONAS:
        z[c] = panel.groupby(["season", "checkpoint"])[c].transform(lambda s: (s - s.mean()) / s.std())
    return z


# ---------------------------------------------------------------- evaluation
def standalone_persona_scores(z):
    log("\n=== Each persona alone: Spearman correlation with rest-of-season / final win %")
    rows = []
    for c in PERSONAS:
        by_cp = {}
        for cp in ["preseason", "25%", "50%", "75%"]:
            d = z[(z.checkpoint == cp)].dropna(subset=[c, "ros"])
            by_cp[cp] = spearmanr(d[c], d.ros).statistic if len(d) > 5 else np.nan
        rows.append({"persona": c, **by_cp, "n_covered": z[c].notna().sum()})
    t = pd.DataFrame(rows).set_index("persona")
    log(t.round(3).to_string())
    return t


def naive_ensemble(z):
    z = z.copy()
    z["crowd_naive"] = z[PERSONAS].mean(axis=1, skipna=True)
    z["n_personas"] = z[PERSONAS].notna().sum(axis=1)
    return z


def learned_combiner(z):
    """OLS on training seasons; predict out-of-sample on HOLDOUT. Coefficients are the
    'learned weights' of the mixture-of-experts layer.
    Four personas (recency, narrative, bandwagon, anchoring) need in-season data and are
    always missing at the preseason checkpoint, so the combiner is fit and used for the
    25/50/75% checkpoints only; preseason keeps only the naive ensemble."""
    fittable = z[z.checkpoint != "preseason"].copy()
    train = fittable[fittable.season < HOLDOUT].dropna(subset=PERSONAS + ["ros"])
    formula = "ros ~ " + " + ".join(PERSONAS) + " + C(checkpoint)"
    m = smf.ols(formula, data=train).fit(cov_type="cluster", cov_kwds={"groups": train.team})
    log(f"\n=== Learned combiner (fit on seasons < {HOLDOUT}, checkpoints 25/50/75%, n={int(m.nobs)})")
    log(m.summary().tables[1].as_text())
    z["crowd_learned"] = np.nan
    predictable = fittable.dropna(subset=PERSONAS)
    z.loc[predictable.index, "crowd_learned"] = m.predict(predictable)
    return z, m


def sanity_checks(z):
    """Collinearity among personas, and leave-one-season-out CV of the learned combiner
    (a single 30-team holdout season is too small to trust on its own)."""
    log("\n=== Sanity check: correlation between persona z-scores (collinearity risk)")
    corr = z[PERSONAS].corr()
    log(corr.round(2).to_string())

    log("\n=== Sanity check: leave-one-season-out CV of the learned combiner (checkpoints 25/50/75%)")
    fittable = z[z.checkpoint != "preseason"]
    rhos = []
    for test_season in sorted(fittable.season.unique()):
        train = fittable[fittable.season != test_season].dropna(subset=PERSONAS + ["ros"])
        test = fittable[fittable.season == test_season].dropna(subset=PERSONAS + ["ros"])
        if len(train) < 50 or len(test) < 10:
            continue
        formula = "ros ~ " + " + ".join(PERSONAS) + " + C(checkpoint)"
        m = smf.ols(formula, data=train).fit()
        pred = m.predict(test)
        rho = spearmanr(pred, test.ros).statistic
        rhos.append({"season": test_season, "n": len(test), "spearman": rho})
        log(f"  held out {test_season}: Spearman = {rho:.3f} (n={len(test)})")
    r = pd.DataFrame(rhos)
    log(f"  mean across seasons: {r.spearman.mean():.3f}  (2026's single-season result was 0.75 -- "
        f"compare against this more honest estimate)")
    r.to_csv(RES / "persona_loso_cv.csv", index=False)


def evaluate_targets(z, games, rs):
    log("\n=== Ensembles vs. stats and vs. the old single-number crowd score")
    log("    Spearman correlation with rest-of-season / final win %, by checkpoint")
    rows = []
    for c in ["crowd_naive", "crowd_learned"]:
        by_cp = {}
        for cp in ["preseason", "25%", "50%", "75%"]:
            d = z[(z.checkpoint == cp) & (z.season < HOLDOUT if c == "crowd_learned" else True)].dropna(subset=[c, "ros"])
            by_cp[cp] = spearmanr(d[c], d.ros).statistic if len(d) > 5 else np.nan
        rows.append({"predictor": c, **by_cp})
        d = z[(z.checkpoint == "75%") & (z.season == HOLDOUT)].dropna(subset=[c, "ros"])
        if len(d) > 5:
            log(f"  {c} HOLDOUT {HOLDOUT} @75%: Spearman = {spearmanr(d[c], d.ros).statistic:.3f} (n={len(d)})")
    t = pd.DataFrame(rows).set_index("predictor")
    log(t.round(3).to_string())

    # playoff series: does the more-favoured team (by each ensemble, at the last regular-season
    # checkpoint of that season) win the series?
    log(f"\n=== Playoff series: share where the ensemble favoured the eventual winner")
    post_rows = []
    for season in sorted(rs.season.unique()):
        post = games[(games.season == season) & (games.season_type == "post-season")].copy()
        if post.empty:
            continue
        post["pair"] = post.apply(lambda r: tuple(sorted((r.home, r.away))), axis=1)
        snap75 = z[(z.season == season) & (z.checkpoint == "75%")].set_index("team")
        for (a, b), s in post.groupby("pair"):
            wa = ((s.home == a) & (s.home_pts > s.away_pts)).sum() + ((s.away == a) & (s.away_pts > s.home_pts)).sum()
            winner = a if wa > len(s) - wa else b
            row = {"season": season, "winner_is_a": winner == a}
            for c in ["crowd_naive", "crowd_learned"]:
                if a in snap75.index and b in snap75.index:
                    row[c] = snap75.loc[a, c] > snap75.loc[b, c]
            post_rows.append(row)
    se = pd.DataFrame(post_rows)
    for c in ["crowd_naive", "crowd_learned"]:
        ok = se.dropna(subset=[c])
        acc = (ok[c] == ok.winner_is_a).mean()
        se_holdout = se[se.season == HOLDOUT].dropna(subset=[c])
        acc_h = (se_holdout[c] == se_holdout.winner_is_a).mean() if len(se_holdout) else np.nan
        log(f"  {c}: all seasons {acc:.3f} (n={len(ok)}), holdout {HOLDOUT} {acc_h:.3f} (n={len(se_holdout)})")
    se.to_csv(RES / "persona_series.csv", index=False)
    return t


def main():
    RES.mkdir(exist_ok=True)
    games, news, wiki, teams = load()
    tg = team_games(games)
    rs = tg[tg.season_type == "regular-season"]
    rs = rs[rs.season >= 2018]  # GDELT team coverage starts 2018
    awards = load_awards()
    people = load_people()
    log(f"people-level coverage: {'none (fetch_gdelt_people_bq.py not run)' if people is None else str(people.name_key.nunique()) + ' players'}")

    panel = build_panel(games, news, wiki, awards, people, rs)
    panel, r2 = add_narrative_residual(panel)
    log(f"[narrative persona] point-diff explains R2 = {r2:.3f} of media tone (residual = the persona)")
    panel.to_csv(RES / "persona_panel_raw.csv", index=False)

    z = zscore(panel)
    standalone_persona_scores(z)
    z = naive_ensemble(z)
    z, model = learned_combiner(z)
    z.to_csv(RES / "persona_panel_scored.csv", index=False)
    sanity_checks(z)
    evaluate_targets(z, games, rs)

    log("\n=== Coverage: % of team-checkpoints with a non-missing value, by persona")
    log((panel[PERSONAS].notna().mean() * 100).round(1).to_string())

    (RES / "persona_log.txt").write_text("\n".join(log_lines), encoding="utf8")


if __name__ == "__main__":
    main()
