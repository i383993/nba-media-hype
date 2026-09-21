-- Daily news coverage per NBA team from the GDELT Global Knowledge Graph (GKG 2.1).
-- An article counts for a team when the team's full name appears in GDELT's AllNames
-- field (every proper name found in the article). The Organizations field was tried
-- first but GDELT's tagger misses some teams entirely (Celtics, Nets, Pelicans).
-- One row per team per day.
--   articles      number of matching articles
--   outlets       distinct news sources (diversity of the "crowd" of journalists)
--   tone_mean     average article tone (GDELT V2Tone, roughly -10 to +10)
--   tone_sd       spread of tone across articles (disagreement vs. herding)
--   tone_pos/neg  average positive / negative word scores
WITH teams AS (
  SELECT * FROM UNNEST([
    STRUCT('ATL' AS team, 'atlanta hawks' AS name), ('BOS', 'boston celtics'),
    ('BKN', 'brooklyn nets'), ('CHA', 'charlotte hornets'), ('CHI', 'chicago bulls'),
    ('CLE', 'cleveland cavaliers'), ('DAL', 'dallas mavericks'), ('DEN', 'denver nuggets'),
    ('DET', 'detroit pistons'), ('GSW', 'golden state warriors'), ('HOU', 'houston rockets'),
    ('IND', 'indiana pacers'), ('LAC', 'los angeles clippers'), ('LAL', 'los angeles lakers'),
    ('MEM', 'memphis grizzlies'), ('MIA', 'miami heat'), ('MIL', 'milwaukee bucks'),
    ('MIN', 'minnesota timberwolves'), ('NOP', 'new orleans pelicans'), ('NYK', 'new york knicks'),
    ('OKC', 'oklahoma city thunder'), ('ORL', 'orlando magic'), ('PHI', 'philadelphia 76ers'),
    ('PHX', 'phoenix suns'), ('POR', 'portland trail blazers'), ('SAC', 'sacramento kings'),
    ('SAS', 'san antonio spurs'), ('TOR', 'toronto raptors'), ('UTA', 'utah jazz'),
    ('WAS', 'washington wizards')
  ])
),
articles AS (
  SELECT
    PARSE_DATE('%Y%m%d', SUBSTR(CAST(DATE AS STRING), 1, 8)) AS day,
    SourceCommonName AS outlet,
    LOWER(AllNames) AS names,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS tone,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(1)] AS FLOAT64) AS pos,
    SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(2)] AS FLOAT64) AS neg
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE _PARTITIONTIME >= TIMESTAMP(@start) AND _PARTITIONTIME < TIMESTAMP(@end)
    AND AllNames IS NOT NULL
    AND REGEXP_CONTAINS(LOWER(AllNames),
      r'hawks|celtics|nets|hornets|bulls|cavaliers|mavericks|nuggets|pistons|warriors|rockets|pacers|clippers|lakers|grizzlies|heat|bucks|timberwolves|pelicans|knicks|thunder|magic|76ers|suns|trail blazers|kings|spurs|raptors|jazz|wizards')
)
SELECT
  t.team, a.day,
  COUNT(*) AS articles,
  COUNT(DISTINCT a.outlet) AS outlets,
  AVG(a.tone) AS tone_mean,
  STDDEV(a.tone) AS tone_sd,
  AVG(a.pos) AS tone_pos,
  AVG(a.neg) AS tone_neg
FROM articles a
JOIN teams t ON STRPOS(a.names, t.name) > 0
GROUP BY t.team, a.day
ORDER BY t.team, a.day
