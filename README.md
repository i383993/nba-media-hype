# When Is the Crowd Wise? Media Hype, Collective Bias and the NBA Betting Market

Research project for the MIT Sloan Sports Analytics Conference 2027 Research Papers
Competition (abstract due **Oct 1, 2026**, full paper Dec 4, 2026).

## Question
Media coverage of NBA teams mixes two things:
1. **Information:** a team is playing well, so coverage is positive.
2. **Collective bias:** narrative, hype, market size, star power; coverage that
   runs ahead of (or behind) what the team is actually doing.

We strip out the part of media tone and attention that recent performance explains.
The leftover **hype residual** is the purely collective component. Then we ask:
- Does it predict results? (Is the crowd wise?)
- Does it predict results **against the closing betting line**? (Does the betting crowd
  over-price hyped teams?)
- Is the market less accurate when media coverage **herds** (everyone piles onto
  the same story), as wisdom-of-crowds theory predicts?
- Past (2018-19 to 2024-25 fitting), present (2025-26 holdout season) and future
  (time-stamped predictions for 2026-27, published before tip-off).

## Data (all public)
| Source | What | Seasons | Script |
|---|---|---|---|
| ESPN scoreboard API | final scores | 2018-19 to 2025-26 | `src/fetch_games.py` |
| ESPN odds API | consensus spread, moneyline, total; open/close lines when available | 2018-19 to 2025-26 | `src/fetch_espn_odds.py` |
| Yahoo Sports via [csdurfee/scrape_yahoo_odds](https://github.com/csdurfee/scrape_yahoo_odds) | closing lines + **% of public bets and money** on each side | 2021-22 to 2024-25 | downloaded to `data/raw/odds_yahoo/` |
| GDELT DOC 2.0 API | daily English-language news article count and average tone per team (what journalists write) | Aug 2018 to Sep 2026 | `src/fetch_gdelt.py` |
| Wikimedia pageviews API | daily views of each team's Wikipedia article (what the public looks up) | Aug 2018 to Sep 2026 | `src/fetch_wiki.py` |

## Pipeline
```bash
pip install -r requirements.txt
cd src
python fetch_games.py          # ~1 hr (one request per day; ESPN rejects date ranges)
python fetch_espn_odds.py      # ~3 hr first time, cached/resumable
python fetch_yahoo.py          # seconds
python fetch_wiki.py           # ~2 min
python fetch_gdelt.py          # many hours: GDELT's real limit for long queries is ~1 request / 10 min
python build_dataset.py        # -> data/team_games.csv
python analysis.py             # -> results/ (tables, log, frozen model results/hype_model.json)
```

## Live test, 2026-27 season (the "future" part)
Every game day, before the first tip-off:
```bash
python fetch_games.py 2027 && python predict_live.py   # -> predictions/<date>.csv
git add predictions && git commit -m "picks <date>" && git push
```
The commit timestamp proves each pick was made before the game. `python score_live.py`
grades all picks so far. The rule is frozen from `results/hype_model.json` and is not
changed during the season.

## Leakage rules
- Media features for a game on day D use coverage through day D-1 only.
- Team form uses earlier games only.
- The hype model is fitted on training seasons only; 2025-26 is held out.

## Status
See `NOTES.md` for the running log, decisions and open issues.
Prior work and how this study differs: `PRIOR_WORK.md`.
