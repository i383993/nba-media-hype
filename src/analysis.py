"""Main analysis: is media 'hype' information, or collective bias the market misprices?

Steps
1. Hype residuals: the part of a team's news tone / attention NOT explained by its
   recent on-court performance. Fitted on training seasons only.
2. Information test: do media variables predict the final margin beyond form?
3. Market test: do media variables predict the result AGAINST THE SPREAD?
   (the closing line already contains everything public; a nonzero effect is bias
   the crowd put into the price, or information it missed)
4. Wisdom-of-crowd test: is the market's error larger when coverage herds
   (attention surges) or when the public's bets are one-sided?
5. Holdout: repeat the key tests on the last season, never used for fitting.

All tests are at the GAME level from the home team's side, with media features as
home-minus-away differences, so each game counts once.
Writes results/*.csv and results/*.txt.
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
HOLDOUT = 2026            # ESPN season label: 2026 = the 2025-26 season
PERF = ["form_margin_10", "form_margin_season", "streak", "last_margin"]

log_lines = []
MODEL = {}  # fitted hype model, saved for live predictions (predict_live.py)


def log(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    log_lines.append(s)


# ---------------------------------------------------------------- 1. hype residuals
HYPE_TARGETS = [("tone_7d", "hype_tone"),      # what journalists write (GDELT tone)
                ("wiki_7d", "hype_wiki"),      # how much the public looks the team up
                ("log_attn_7d", "hype_attn")]  # how much journalists write (GDELT volume)


def available(tg):
    return [(t, n) for t, n in HYPE_TARGETS if t in tg and tg[t].notna().mean() > 0.5]


def add_hype(tg):
    tg = tg.copy()
    if "attn_7d" in tg and tg.attn_7d.notna().any():
        tg["log_attn_7d"] = np.log1p(tg.attn_7d)
    rhs = " + ".join(PERF) + " + C(season)"
    for target, name in available(tg):
        train = tg[tg.season < HOLDOUT].dropna(subset=PERF + [target])
        fit = smf.ols(f"{target} ~ {rhs}", data=train).fit()
        log(f"[hype] {target} explained by performance: R2 = {fit.rsquared:.3f}")
        season_fe = {s: fit.params.get(f"C(season)[T.{s}]", 0.0) for s in tg.season.unique()}
        default_fe = float(np.mean([v for k, v in season_fe.items() if k < HOLDOUT]))
        # holdout / future seasons have no dummy: use the training average
        # (it cancels anyway in the home-minus-away differences used for testing)
        pred = (fit.params["Intercept"] + sum(fit.params[c] * tg[c] for c in PERF)
                + tg.season.map(season_fe).where(tg.season < HOLDOUT, default_fe))
        tg[name] = tg[target] - pred
        # split into persistent team "brand" bias and within-team narrative swings
        brand = tg[tg.season < HOLDOUT].groupby("team")[name].mean()
        tg[f"{name}_brand"] = tg.team.map(brand)
        tg[f"{name}_swing"] = tg[name] - tg[f"{name}_brand"]
        MODEL[name] = {"target": target, "intercept": fit.params["Intercept"] + default_fe,
                       "coef": {c: fit.params[c] for c in PERF}, "brand": brand.to_dict(),
                       "r2": fit.rsquared}
    return tg


def to_games(tg):
    """Home-side rows with home-minus-away media differences."""
    media = [c for c in tg.columns if c.startswith(("hype_", "tone_", "attn_", "log_attn", "wiki_"))]
    home = tg[tg.is_home == 1].set_index("espn_id")
    away = tg[tg.is_home == 0].set_index("espn_id")
    g = home.copy()
    for c in media + PERF:
        g[f"d_{c}"] = home[c] - away[c]
    return g.reset_index()


def fit(formula, df, label, min_n=200):
    names = set(re.findall(r"[A-Za-z_]\w*", formula))
    df = df.dropna(subset=[c for c in df.columns if c in names])
    if len(df) < min_n:
        log(f"\n=== {label}: skipped, only {len(df)} games with complete data")
        return None
    m = smf.ols(formula, data=df).fit(cov_type="cluster", cov_kwds={"groups": df["date"].astype(str)})
    log(f"\n=== {label}  (n={int(m.nobs)})")
    log(m.summary().tables[1].as_text())
    return m


# ---------------------------------------------------------------- 4. crowd accuracy
def crowd_accuracy(g, surge):
    g = g.dropna(subset=["ats_margin", surge])
    g = g.assign(abs_err=g.ats_margin.abs(),
                 herding=pd.qcut(g[surge].abs(), 3, labels=["low", "mid", "high"]))
    side = np.sign(g[surge])  # +1 when the home team's attention surged more
    t = g.groupby("herding", observed=True).agg(
        games=("abs_err", "size"),
        market_abs_error=("abs_err", "mean"),
        # result vs the line for the team whose attention surged more
        surging_side_ats=("ats_margin", lambda s: (s * side[s.index]).mean()),
        surging_side_cover=("ats_margin", lambda s: ((s * side[s.index]) > 0).mean()),
    )
    log(f"\n=== Market error by attention herding (|{surge}| terciles)")
    log(t.round(3).to_string())
    t.to_csv(RES / f"crowd_accuracy_by_{surge}.csv")
    if g.pub_bets_home.notna().any():
        pb = g.dropna(subset=["pub_bets_home"]).copy()
        pb["public_side"] = np.sign(pb.pub_bets_home - 50)
        pb["lopsided"] = pd.cut((pb.pub_bets_home - 50).abs(), [0, 10, 20, 50],
                                labels=["<60%", "60-70%", ">70%"], include_lowest=True)
        t2 = pb.groupby("lopsided", observed=True).agg(
            games=("abs_err", "size"),
            market_abs_error=("abs_err", "mean"),
            public_side_cover=("ats_margin", lambda s: ((s * pb.loc[s.index, "public_side"]) > 0).mean()),
        )
        log("\n=== Public side's cover rate by how one-sided the public's bets were")
        log(t2.round(3).to_string())
        t2.to_csv(RES / "public_side_by_lopsidedness.csv")


# ---------------------------------------------------------------- 5. fade-the-hype check
def fade_hype(g, label, col, q=0.8, cut=None):
    """Bet the LESS hyped side when the hype gap is in the top (1-q) share.
    `cut` lets the holdout reuse the threshold chosen on training data."""
    g = g.dropna(subset=[col, "cover"])
    if len(g) < 100:
        log(f"\n=== Fade the hype [{col}] ({label}): skipped, {len(g)} games")
        return {"measure": col, "sample": label, "threshold": cut, "bets": len(g)}
    cut = g[col].abs().quantile(q) if cut is None else cut
    picks = g[g[col].abs() >= cut]
    won = np.where(picks[col] < 0, picks.cover, 1 - picks.cover)
    rate = won.mean()
    rng = np.random.default_rng(0)
    boot = [rng.choice(won, len(won)).mean() for _ in range(2000)]
    roi = rate * (100 / 110) - (1 - rate)  # standard -110 pricing
    log(f"\n=== Fade the hype [{col}] ({label}): top {round((1-q)*100)}% hype gaps, n={len(won)}, "
        f"win rate {rate:.3f} (95% CI {np.percentile(boot, 2.5):.3f}-{np.percentile(boot, 97.5):.3f}), "
        f"ROI at -110 {roi:+.3f}. Break-even is 0.524.")
    return {"measure": col, "sample": label, "threshold": cut, "bets": len(won), "win_rate": rate,
            "ci_low": np.percentile(boot, 2.5), "ci_high": np.percentile(boot, 97.5), "roi": roi}


def main():
    RES.mkdir(exist_ok=True)
    tg = pd.read_csv(ROOT / "data" / "team_games.csv", parse_dates=["date"])
    tg = tg[~tg.season_type.str.startswith("play-in")]
    log(f"team-games {len(tg)}, seasons {sorted(tg.season.unique())}, "
        f"with line {tg.spread.notna().mean():.3f}")
    tg = add_hype(tg)
    g = to_games(tg)
    train, test = g[g.season < HOLDOUT], g[g.season == HOLDOUT]
    perf = " + ".join(f"d_{c}" for c in PERF)

    hype = [n for _, n in available(tg)]
    raw = [t for t, _ in available(tg)]
    d_hype = " + ".join(f"d_{h}" for h in hype)
    d_raw = " + ".join(f"d_{t}" for t in raw)
    log(f"media measures used: {raw}")

    # 2. information: does media predict the final margin beyond form / beyond the line?
    fit(f"margin ~ {perf}", train, "Info baseline: margin ~ form")
    fit(f"margin ~ {perf} + {d_raw}", train, "Info: margin ~ form + raw media")
    fit(f"margin ~ exp_margin + {d_raw}", train, "Info vs market: margin ~ line + raw media")

    # 3. market: against the spread
    fit(f"ats_margin ~ {d_hype}", train, "Market: ATS ~ hype (train)")
    parts = " + ".join(f"d_{h}_brand + d_{h}_swing" for h in hype)
    fit(f"ats_margin ~ {parts}", train, "Market: ATS ~ brand vs swing hype (train)")
    fit(f"ats_margin ~ {d_hype} + {perf}", train, "Market: ATS ~ hype + form (train)")
    if len(test):
        fit(f"ats_margin ~ {d_hype}", test, f"HOLDOUT {HOLDOUT}: ATS ~ hype")
    if "line_move" in g and g.line_move.notna().sum() > 200:
        fit(f"ats_margin ~ line_move + {d_hype}", g, "Line movement (open->close) vs ATS, all seasons")

    # 4. crowd accuracy under herding
    for surge in ("d_wiki_surge", "d_attn_surge"):
        if surge in train and train[surge].notna().mean() > 0.5:
            crowd_accuracy(train, surge)

    # 5. fade the hype: threshold fixed on training data, then applied to the holdout
    rows = []
    for h in hype:
        r = fade_hype(train, "train", f"d_{h}")
        rows.append(r)
        if len(test):
            rows.append(fade_hype(test, f"holdout {HOLDOUT}", f"d_{h}", cut=r["threshold"]))
    pd.DataFrame(rows).to_csv(RES / "fade_hype.csv", index=False)
    MODEL["fade_threshold"] = {r["measure"]: r["threshold"] for r in rows if r["sample"] == "train"}
    (RES / "hype_model.json").write_text(json.dumps(MODEL, indent=1, default=float), encoding="utf8")

    (RES / "analysis_log.txt").write_text("\n".join(log_lines), encoding="utf8")


if __name__ == "__main__":
    main()
