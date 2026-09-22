"""Daily news coverage of every award candidate (players and coaches) from GDELT via BigQuery.

Only the 28 days before each prediction checkpoint are read, which keeps the scan inside
BigQuery's free tier. Checkpoints per season: opening night, 25 / 50 / 75 % of the regular
season, and the last regular-season day. A candidate is 'mentioned' when GDELT's V2Persons
field lists the name (GDELT stores names without accents, like awards.csv's name_key).

    python fetch_gdelt_people_bq.py --project YOUR_PROJECT            # dry run (free)
    python fetch_gdelt_people_bq.py --project YOUR_PROJECT --run

Output: data/raw/gdelt_people.csv  (name_key, day, articles, outlets, tone_mean, tone_sd)
"""
import argparse
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
WINDOW = 28


def checkpoints():
    """(season, label, date) for each prediction checkpoint (regular season, 2017-18 onward)."""
    g = pd.read_csv(RAW / "games.csv", parse_dates=["date"])
    reg = g[g.season_type == "regular-season"]
    rows = []
    for season, s in reg.groupby("season"):
        if season < 2018:
            continue
        start, end = s.date.min(), s.date.max()
        for label, frac in [("preseason", 0), ("25%", .25), ("50%", .5), ("75%", .75), ("end", 1)]:
            rows.append((season, label, (start + (end - start) * frac).normalize()))
    return rows


def build_sql():
    cps = checkpoints()
    ranges = " OR ".join(
        f"(_PARTITIONTIME >= TIMESTAMP('{d - pd.Timedelta(days=WINDOW):%Y-%m-%d}') "
        f"AND _PARTITIONTIME < TIMESTAMP('{d:%Y-%m-%d}'))" for _, _, d in cps)
    return f"""
WITH docs AS (
  SELECT PARSE_DATE('%Y%m%d', SUBSTR(CAST(DATE AS STRING), 1, 8)) AS day,
         SourceCommonName AS outlet,
         LOWER(V2Persons) AS persons,
         SAFE_CAST(SPLIT(V2Tone, ',')[SAFE_OFFSET(0)] AS FLOAT64) AS tone
  FROM `gdelt-bq.gdeltv2.gkg_partitioned`
  WHERE ({ranges}) AND V2Persons IS NOT NULL
    AND REGEXP_CONTAINS(LOWER(V2Persons), @pattern)
)
SELECT n AS name_key, d.day, COUNT(*) AS articles, COUNT(DISTINCT d.outlet) AS outlets,
       AVG(d.tone) AS tone_mean, STDDEV(d.tone) AS tone_sd
FROM docs d, UNNEST(@names) AS n
WHERE STRPOS(d.persons, n) > 0
GROUP BY n, d.day
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--run", action="store_true")
    ap.add_argument("--max-tb", type=float, default=0.15)
    args = ap.parse_args()

    names = sorted({n.lower() for n in pd.read_csv(RAW / "awards.csv").name_key.dropna()})
    import re
    pattern = "|".join(re.escape(n) for n in names)
    cfg = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ArrayQueryParameter("names", "STRING", names),
        bigquery.ScalarQueryParameter("pattern", "STRING", pattern)])
    sql = build_sql()
    client = bigquery.Client(project=args.project)
    cfg.dry_run, cfg.use_query_cache = True, False
    tb = client.query(sql, job_config=cfg).total_bytes_processed / 1e12
    print(f"{len(names)} names, {len(checkpoints())} windows of {WINDOW} days: scan {tb:.3f} TB "
          f"(free tier 1 TB/month)")
    if not args.run:
        return
    if tb > args.max_tb:
        raise SystemExit(f"refusing: {tb:.3f} TB > --max-tb {args.max_tb}")
    cfg.dry_run, cfg.use_query_cache = False, True
    df = client.query(sql, job_config=cfg).to_dataframe()
    df.to_csv(RAW / "gdelt_people.csv", index=False)
    print("saved", len(df), "name-days;", df.name_key.nunique(), "names with coverage")


if __name__ == "__main__":
    main()
