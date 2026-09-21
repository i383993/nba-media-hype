# Prior work: interview language vs. performance

## Closest paper (must cite and differentiate)
**Oved, Feder & Reichart (2020). "Predicting In-Game Actions from Interviews of NBA Players." *Computational Linguistics* 46(3).**
arXiv:1910.11292 · code: https://github.com/nadavo/mood

- Data: ASAPsports.com transcripts (same source we planned) + basketball-reference play-by-play
- 36 all-star players, 2004-05 through June 2018, mostly **playoff** interviews; 1,337 interviews, 5,226 interview-period pairs
- Task: **binary** classification of whether a player is above/below his recent mean on 7 metrics (points, assists/turnovers, shot distance, 2pt/3pt share, fouls, etc.)
- Models: bag-of-words regression, LSTM, CNN, BERT; LDA for interpretation
- Result: text beats metrics-only baselines (up to ~7 accuracy points on some tasks); text + metrics is best
- **Players only; no coaches**
- No comparison with betting markets / Vegas lines or player props
- No causal framing; interpretation is post-hoc via topics on a black-box model
- Future work they list: time trends, player interactions, joint metrics

## Other related work
- Sci. Reports 2025: NBA players' social-media language -> Big Five personality -> technical fouls (https://www.nature.com/articles/s41598-025-99667-5)
- ACM 2021: Twitter fan sentiment vs. NBA player performance (fan language, not player language)
- AFL post-match interviews: linguistic (Appraisal theory) analysis, no performance prediction
- iMiGUE-Speech (arXiv 2602.21464): winners vs. losers sentiment in post-match interviews (descriptive)

## Tennis-specific prior work (if we pivot)
- SPIE 2024, "Analysis and prediction of tennis players' match performance with sentiment analysis": players' **tweets** + VADER + decision trees. Not press conferences, no betting-market test.
- arXiv 2506.02283, "Sounding Like a Winner? Prosodic Differences in Post-Match Interviews": audio pitch/loudness classifies whether the athlete **just** won or lost. Describes the match already played; does not predict the next one.
- No study found that uses press-conference transcripts to predict the **next** match against closing betting odds.

## Data coverage check (ASAP Sports, 2026-09-21)
- **NBA (category 11):** since 2018, only 3-6 playoff series per year (Finals, conference finals, some Warriors series) plus All-Star and Draft. **No regular season.** Too thin for a betting-line test.
- **Tennis (category 7):** 35-37 tournaments per year (all four Slams, Masters 1000s, WTA 1000s, Finals). The 2026 US Open alone has 145 transcripts. Players give post-match press conferences after most main-draw matches.
- Tennis odds: tennis-data.co.uk (ATP since 2000, WTA since 2007, several bookmakers; blocks plain curl, may need a browser download), Kaggle mirror, Valuebetennis (open/close odds since 2021).
- Tennis match stats: JeffSackmann/tennis_atp and tennis_wta **no longer on GitHub** (only tennis_MatchChartingProject remains); alternative is Tennismylife/TML-Database.

## Full 2025 ASAP count by sport (src/count_coverage.py -> data/coverage_2025.csv)
| Sport | Pro-level transcripts | Notes |
|---|---|---|
| Golf | ~2,775 men's pro + 787 LPGA (4,443 total) | after most rounds; interviewees skew to leaders |
| Tennis | 1,582 | 37 tournaments; winners and losers both talk |
| MLB | 648 | All-Star + postseason only |
| NBA | 311 | 195 of them are the Finals |
| NASCAR / IndyCar | 178 / 155 | no F1 on ASAP |
| NFL | 3 | college football media days dominate |
| Hockey, soccer, boxing, cricket | 0-13 | effectively none |

Outside ASAP: FIA posts every F1 press conference (~100-120/yr, top-3 only after quali/race); NFL transcripts are scattered across 32 team sites, most of which block scripts; FIFA/Premier League publish video or summaries, not transcripts.

## Pivot idea: media / crowd sentiment ("wisdom of the crowd") vs. outcomes
- **Hong & Skiena (2010), "The Wisdom of Bookies? Sentiment Analysis Versus the NFL Point Spread," ICWSM.** Blogs, Twitter and news vs. NFL lines 2006-09; a sentiment strategy picked ~60% of ~30 games/yr against the spread. Small bet count, pre-2010 data, raw sentiment (no separation of information vs. bias).
- **Sinha, Dyer, Gimpel & Smith (2013), "Predicting the NFL using Twitter"** (arXiv 1310.6998). Tweet volume/sentiment matches or beats stats-based features for NFL winners and spread.
- **Schumaker et al. (2016/2017), Decision Support Systems.** Premier League wins/spread from Twitter sentiment; NFL "regional angst" with stock-charting techniques.
- **Feddersen, Humphreys & Soebbing, "Sentiment Bias in NBA Betting"** (33,000 games 1981-2012). Bookmakers shade spreads for *popular* teams (proxied by attendance and All-Star votes). Popularity proxies, not text.
- **Barker (2025), "Hoop Hype"** (Allegheny undergrad thesis). NewsAPI + TextBlob to measure NBA media sentiment by team; no outcome prediction, no betting lines.
- Tennis tweets (SPIE 2024), soccer tweets + odds (ScienceDaily 2017 summary).

What has NOT been done (as far as found):
1. **Decomposition:** split media tone into the part explained by performance (information) and the leftover "hype/narrative" residual (pure collective bias), then test each separately.
2. **Multi-year NBA news (not Twitter) vs. closing lines, 2018-2026.** Twitter data is no longer obtainable; GDELT news tone is free and daily since 2015-2017.
3. **When is the crowd wise?** Test the Surowiecki condition directly: is the media signal more accurate when coverage is diverse/independent (many outlets, dispersed tone) than when it herds (one dominant narrative)?
4. **A genuine forward test:** publish time-stamped predictions for the 2026-27 NBA season before tip-off (Oct 2026) and score them live by the Dec paper deadline and the March 2027 conference.

Data check (2026-09-21): GDELT DOC 2.0 API returns daily article counts and tone per query back to at least Jan 2018 (limit: 1 request / 5 s).

## Gaps we can fill
1. **Market test:** does interview language contain information that betting lines and player-prop lines have *not* already priced in? That is the practical bar for teams and bettors.
2. **Out-of-sample replication:** 2018-19 through 2025-26 is data their model never saw. Does the finding still hold?
3. **Coaches:** coach press-conference language vs. team results against the spread.
4. **Interpretable, pre-registered features** (confidence/hedging, "we" vs "I", injury/fatigue mentions, blame) instead of a black box, so results tell a coach *what* to listen for.
