"""Daily GDELT news coverage per NBA team via Google BigQuery (replaces the rate-limited API).

    gcloud auth application-default login          # once, in your own terminal
    python fetch_gdelt_bq.py --project YOUR_PROJECT # dry run: prints how much it would scan
    python fetch_gdelt_bq.py --project YOUR_PROJECT --run

Queries run year by year. Every chunk is dry-run first (free), and the script
refuses to start if the total would exceed --max-tb (default 0.9 TB, inside
BigQuery's 1 TB/month free tier). Output: data/raw/gdelt_bq.csv
"""
import argparse
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parent.parent
SQL = (Path(__file__).parent / "gdelt_bq.sql").read_text()
CHUNKS = [(f"{y}-08-01", f"{y + 1}-08-01") for y in range(2018, 2026)] + [("2026-08-01", "2026-09-21")]


def config(start, end, dry):
    return bigquery.QueryJobConfig(
        dry_run=dry, use_query_cache=not dry,
        query_parameters=[bigquery.ScalarQueryParameter("start", "STRING", start),
                          bigquery.ScalarQueryParameter("end", "STRING", end)])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--run", action="store_true", help="actually run (default: dry run only)")
    ap.add_argument("--max-tb", type=float, default=0.9)
    args = ap.parse_args()
    client = bigquery.Client(project=args.project)

    sizes = []
    for start, end in CHUNKS:
        tb = client.query(SQL, job_config=config(start, end, True)).total_bytes_processed / 1e12
        sizes.append(tb)
        print(f"{start} to {end}: {tb:.3f} TB")
    total = sum(sizes)
    print(f"TOTAL {total:.3f} TB (free tier: 1 TB per month; beyond that ~$6.25/TB)")
    if not args.run:
        print("dry run only; add --run to execute")
        return
    if total > args.max_tb:
        raise SystemExit(f"refusing: {total:.2f} TB > --max-tb {args.max_tb}")

    out = ROOT / "data" / "raw" / "gdelt_bq.csv"
    frames = []
    for start, end in CHUNKS:
        df = client.query(SQL, job_config=config(start, end, False)).to_dataframe()
        frames.append(df)
        print(f"{start}: {len(df)} team-days", flush=True)
        pd.concat(frames).to_csv(out, index=False)  # save progress after every chunk
    print("saved", out)


if __name__ == "__main__":
    main()
