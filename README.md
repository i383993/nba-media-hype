# Buzz Kill: Media Attention Surges as a Contrarian Signal of NBA Team Trajectory

Research project for the MIT Sloan Sports Analytics Conference 2027 Research Papers
Competition (abstract due Oct 1, 2026; full paper Dec 4, 2026).

## The question
"Wisdom of the crowd" rankings — media coverage, fan attention, all-time-player debates —
assume collective attention tracks who is actually playing well. We test this for the NBA:
does the aggregate attention of journalists (news coverage) and fans (Wikipedia interest)
predict team performance? A naive test fails outright (`src/mvp_check.py`): the most-covered
MVP candidate in news matched the actual winner in **0 of the last 9 seasons**.

The sharper question: is collective attention just noise, or does it carry real information
once measured correctly? We define **buzz** — a team's current attention relative to its own
trailing three-year baseline, which strips out fixed market-size effects (the Lakers are
always covered a lot, hype or not) — and test it against team trajectory.

**Finding:** media buzz is a significant, robust **negative** predictor of performance.
Controlling for a team's current point differential *and* its last-10-game form, a
one-standard-deviation buzz surge is associated with about one fewer win over an 82-game
season (p=0.013, n=941 team-checkpoints) and cuts a playoff team's odds of winning its
series to roughly 57% of baseline (p=0.006, n=151 series). See `results/buzz_headline_table.csv`
and `results/crowd_teams_beyond_stats.csv` for the full numbers, and `results/persona_log.txt`
for the underlying mixture-of-personas robustness work.

## Data (all public)
| Source | What | Coverage | Script |
|---|---|---|---|
| ESPN scoreboard API | game results | 2015-16 to 2025-26 | `src/fetch_games.py` |
| GDELT (via Google BigQuery) | daily news article count, outlet count, and tone per team | Jul 2015 – Sep 2026 | `src/fetch_gdelt_bq.py`, `src/gdelt_bq.sql` |
| GDELT (via BigQuery) | daily news mentions of individual award candidates | 2018-19 onward | `src/fetch_gdelt_people_bq.py` |
| Wikimedia pageviews API | daily views of each team's Wikipedia article | Jul 2015 – Sep 2026 | `src/fetch_wiki.py` |
| pr.nba.com | official MVP/ROY/DPOY/Sixth Man/Most Improved/Clutch/Coach of the Year voting (rebuilt from each media voter's ballot PDF) | 2017-18 to 2025-26 | `src/fetch_awards.py` |

An earlier phase of this project (`src/fetch_espn_odds.py`, `src/fetch_yahoo.py`,
`src/build_dataset.py`, `src/analysis.py`) tested interview/media language against the NBA
betting market. That question is answered (media hype does not beat the closing line — see
git history) and isn't part of the current thesis; the scripts are kept for reproducibility
and because `games.csv` and the GDELT/Wikipedia pulls carry over into the current analysis.

## Pipeline
```bash
pip install -r requirements.txt
cd src
python fetch_games.py                                    # game results
python fetch_gdelt_bq.py --project YOUR_GCP_PROJECT --run # team-level news (dry-runs first; free tier)
python fetch_wiki.py                                      # team-level Wikipedia attention
python fetch_awards.py                                    # official award voting
python fetch_gdelt_people_bq.py --project YOUR_GCP_PROJECT --run  # player-level news
python crowd_teams.py      # -> results/crowd_teams_*.csv : crowd vs. stats at standings/
                            #    champion/playoff-series prediction, plus the beyond-stats
                            #    buzz regressions (with and without a recency control)
python persona_model.py    # -> results/persona_*.csv : decomposes "the crowd" into 7 named
                            #    cognitive-bias personas, combined by a naive average and a
                            #    learned linear combiner, validated with leave-one-season-out CV
python mvp_check.py        # -> results/mvp_naive_pick.csv : the introduction's naive-MVP-pick illustration
```
Verified reproducible end to end from a clean clone (see NOTES.md).

## Leakage rules
Every feature for a prediction at date D uses only games played and attention/coverage
recorded strictly before D. The persona model's `star_power` uses only players who received
award votes in a *prior* season, so it cannot leak the season being predicted.

## Status
`NOTES.md` — running decision log, data-source notes, and known limitations.
`PRIOR_WORK.md` — related research and how this project differs from it.
