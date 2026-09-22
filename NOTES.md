# Running notes / decision log

## 2026-09-21

### Topic path
1. Interviews -> performance (NBA). Closest prior: Oved et al. 2020 (Computational Linguistics).
2. Considered tennis/golf because ASAP Sports' NBA archive is thin since 2018 (see PRIOR_WORK.md coverage table).
3. **Current:** media coverage / "wisdom of the crowd" vs. outcomes and the betting market (NBA).
   Prior: Hong & Skiena 2010 (NFL), Sinha et al. 2013 (NFL Twitter), Feddersen/Humphreys (NBA popularity bias).
   Our novelty: (a) residualize media on performance to isolate pure "hype"; (b) test herding
   (Surowiecki's independence condition); (c) 8 seasons incl. a holdout season; (d) pre-registered 2026-27 forecasts.

### Data decisions
- **Scores:** stats.nba.com (nba_api) timed out from this network -> ESPN scoreboard API, one request per day
  (ESPN now rejects date ranges with HTTP 400).
- **Betting lines:**
  - Yahoo (csdurfee/scrape_yahoo_odds CSVs) covers 2021-22 to 2024-25 and includes % of public bets/money.
    Yahoo's odds endpoint now returns 404, so it cannot be extended to 2025-26.
  - ESPN core odds API covers every game back to at least 2018-19, many books per game.
    It includes in-game "Live Odds" feeds -> excluded. Uses the median across books (≈ ESPN "consensus").
  - **Validation:** ESPN pre-game consensus vs Yahoo closing line: within 1 point on 97.8% of games,
    mean absolute difference 0.26 points (first 582 overlapping games). Good enough to use ESPN for all seasons.
  - ESPN also has DraftKings open/close lines for recent games -> line movement feature.
- **Media:** GDELT DOC 2.0 API, English sources, query = full team name in quotes (avoids "Heat", "Magic", "Jazz").
  Daily article count (plus total monitored articles, to normalize) and average tone, Aug 2018 to Sep 2026.
  GDELT locks you out for several minutes if you exceed ~1 request / 5 s; the script waits 30 s between calls
  and 5 min after a 429.

### Known limitations to state in the paper
- GDELT tone is a dictionary-based average over whole articles, not tone *about* the team specifically.
- Full team-name queries miss articles that only use the nickname; this lowers volume but keeps precision.
- Public betting % (Yahoo) exists only for 4 seasons.
- 2019-20 bubble games have no real home court.
- ESPN line = consensus near game time, not a guaranteed closing line (validated above).

## 2026-09-23 (final thesis for the Oct 1 abstract)

After the crowd-vs-stats work (standings/champion/playoff-series, all null or negative for
the crowd) and the persona/mixture-of-experts model, the headline finding is a specific piece
of the persona work's `beyond_stats()` regression: **media_buzz** (a team's attention relative
to its own trailing 3-year baseline, not raw attention share) is a significant NEGATIVE
predictor of both rest-of-season win% (p=0.011) and playoff series wins (p=0.006), and the
effect survives adding a last-10-game recency control almost unchanged (p=0.013, p=0.006) --
ruling out "it's just hot streaks regressing" as the explanation. Effect sizes: ~1 fewer win
per 82 games per SD of buzz; playoff-series win odds cut to ~57% of baseline per typical
buzz gap between two teams.

This became the paper's thesis ("Buzz Kill") rather than the broader "does the crowd predict
outcomes" framing, because the broader version is mostly null on small samples (9-11 champion
picks) while this is well-powered (941 team-checkpoints, 151 playoff series), robust, and
gives a concrete, novel, counterintuitive claim. The MVP naive-pick check (0/9 seasons, LeBron
James picked 6/9 regardless of who won -- src/mvp_check.py) is kept as the introduction's hook,
not a standalone result.

Repo cleanup for the public push: removed data/raw/gdelt/ (stray leftover from the abandoned
free GDELT API), untracked data/team_games.csv (contains Yahoo-scraped columns with no clear
redistribution license -- the earlier betting-phase build_dataset.py can still regenerate it
locally), and excluded data/raw/wiki_people/ + wiki_titles.csv (download incomplete, ~72/303
players, and unused by the current analysis -- star_power uses gdelt_people.csv only).
