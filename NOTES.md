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
