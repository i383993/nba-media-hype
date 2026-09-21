"""Official NBA regular-season award voting (pr.nba.com PDFs).

For each season, download every award's *Voter-Selections* PDF (each media
voter's ballot) and rebuild the totals from the ballots. Ballots exist as text for
every season, while the totals PDFs change format and are sometimes images.
One row per candidate: name, team, points, votes by ballot place.
Output: data/raw/awards.csv
"""
import io
import re
import time
from pathlib import Path

import pandas as pd
import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
HEADERS = {"User-Agent": "Mozilla/5.0 (academic research)"}
PAGE = "https://pr.nba.com/voting-results-{season}-nba-regular-season-awards/"
AWARD = {  # substring of the PDF file name -> short code (All-NBA/-Defensive/-Rookie teams excluded)
    "mvp": "MVP", "most-valuable": "MVP", "rookie-of-the-year": "ROY",
    "defensive-player": "DPOY", "sixth-man": "SMOY", "most-improved": "MIP",
    "clutch": "CLUTCH", "coach-of-the-year": "COY",
}
# ballot points by place; MVP uses a 5-deep ballot, the others 3-deep
POINTS = {"MVP": [10, 7, 5, 3, 1]}
DEFAULT_POINTS = [5, 3, 1]
# results table rows: "Name, Team 79 18 2 0 0 926" or "Name (Team) 65 27 6 2 0 875"
ROWS = [re.compile(r"^(?P<name>[^,()]+?),\s*(?P<team>[A-Za-z .'-]+?)\s+(?P<nums>(?:\d+\s+)*\d+)$"),
        re.compile(r"^(?P<name>[^,()]+?)\s*\((?P<team>[^)]+)\)\s+(?P<nums>(?:\d+\s+)*\d+)$"),
        # 2017-19: "Harden, James (HOU) 86 15 0 0 0 965"
        re.compile(r"^(?P<last>[^,()]+?),\s*(?P<first>[^,()]+?)\s*\((?P<team>[A-Z ]{2,5})\)\s+(?P<nums>(?:\d+\s+)*\d+)$")]
# ballot entries: "Jokic, Nikola (DEN)"
BALLOT = re.compile(r"([A-Z][\w.'\-]+(?: Jr\.| Sr\.| II| III| IV)?), ([A-Z][\w.'\- ]*?) ?\(([A-Z]{2,4})\)")


def season_label(end_year):
    return f"{end_year - 1}-{str(end_year)[2:]}"


def pdf_text(pdf_bytes):
    text = "\n".join(p.extract_text() or "" for p in PdfReader(io.BytesIO(pdf_bytes)).pages)
    return text.replace("\xa0", " ").replace("‐", "-").replace("(OK C)", "(OKC)")


CITIES = ["Atlanta", "Boston", "Brooklyn", "Charlotte", "Chicago", "Cleveland", "Dallas", "Denver",
          "Detroit", "Golden State", "Houston", "Indiana", "LA Clippers", "LA Lakers", "Los Angeles",
          "Memphis", "Miami", "Milwaukee", "Minnesota", "New Orleans", "New York", "Oklahoma City",
          "Orlando", "Philadelphia", "Phoenix", "Portland", "Sacramento", "San Antonio", "Toronto",
          "Utah", "Washington"]
CITY_SPLIT = re.compile(r",\s*(" + "|".join(sorted(map(re.escape, CITIES), key=len, reverse=True)) + r")\b\s*")


def parse_city_ballots(text, award):
    """2024-25+ ballots: 'Voter, Affiliation First Last, City First Last, City ...'."""
    pts = POINTS.get(award, DEFAULT_POINTS)
    lines = []
    for line in text.splitlines():
        parts = CITY_SPLIT.split(line)  # [lead+pick1, city1, pick2, city2, ...]
        if len(parts) == 2 * len(pts) + 1:
            lines.append(parts)
    # names seen in places 2..n are clean; use them to cut pick 1 off the voter/affiliation text
    known = {parts[i].strip() for parts in lines for i in range(2, len(parts) - 1, 2)}
    totals, n_ballots = {}, 0
    for parts in lines:
        lead = parts[0].strip()
        first = next((k for k in sorted(known, key=len, reverse=True) if lead.endswith(" " + k)), None)
        if first is None:
            continue
        picks = [(first, parts[1])] + [(parts[i].strip(), parts[i + 1]) for i in range(2, len(parts) - 1, 2)]
        n_ballots += 1
        for place, key in enumerate(picks):
            totals.setdefault(key, [0] * len(pts))[place] += 1
    return [{"name": n, "team": tm, "points": sum(c * p for c, p in zip(v, pts)),
             "first_place": v[0], "place_votes": " ".join(map(str, v))}
            for (n, tm), v in totals.items()], n_ballots


def fetch_text(url):
    try:
        return pdf_text(requests.get(url, headers=HEADERS, timeout=60).content)
    except Exception as e:  # a few links point to broken or non-PDF files
        print("  unreadable:", url.rsplit("/", 1)[-1], type(e).__name__)
        return ""


def parse_ballots(text, award):
    """Rebuild totals from individual ballots (used when the results PDF is an image)."""
    pts = POINTS.get(award, DEFAULT_POINTS)
    totals, n_ballots = {}, 0
    for line in text.splitlines():
        picks = BALLOT.findall(line)
        if len(picks) != len(pts):
            continue  # header or wrapped line
        n_ballots += 1
        for place, (last, first, team) in enumerate(picks):
            t = totals.setdefault((f"{first} {last}", team), [0] * len(pts))
            t[place] += 1
    return [{"name": n, "team": tm, "points": sum(c * p for c, p in zip(v, pts)),
             "first_place": v[0], "place_votes": " ".join(map(str, v))}
            for (n, tm), v in totals.items()], n_ballots


def parse(text):
    rows = []
    for line in text.splitlines():
        m = next((r.match(line.strip()) for r in ROWS if r.match(line.strip())), None)
        if not m:
            continue
        nums = [int(x) for x in m["nums"].split()]
        g = m.groupdict()
        name = g.get("name") or f'{g["first"].strip()} {g["last"].strip()}'
        rows.append({"name": name.strip(), "team": m["team"].strip(),
                     "points": nums[-1], "first_place": nums[0] if len(nums) > 1 else None,
                     "place_votes": " ".join(map(str, nums[:-1]))})
    return rows


def main(first=2018, last=2026):
    out = []
    for end_year in range(first, last + 1):
        season = season_label(end_year)
        r = requests.get(PAGE.format(season=season), headers=HEADERS, timeout=60)
        if r.status_code != 200:
            print(season, "page not found")
            continue
        pdfs = sorted(set(re.findall(r'href="([^"]+\.pdf)"', r.text)))
        by_award = {}
        for url in pdfs:
            fname = url.lower().rsplit("/", 1)[-1]
            award = next((code for key, code in AWARD.items() if key in fname), None)
            if award and "all-" not in fname:
                kind = "ballots" if "selections" in fname else "totals"
                by_award.setdefault(award, {})[kind] = url
        for award, files in by_award.items():
            rows, n_ballots, source = [], 0, None
            if "ballots" in files:
                text = fetch_text(files["ballots"])
                rows, n_ballots = parse_ballots(text, award)
                if n_ballots < 50:
                    rows, n_ballots = parse_city_ballots(text, award)
                source = "ballots"
            if n_ballots < 50 and "totals" in files:  # ballot layout not parsed: use official totals
                rows, n_ballots, source = parse(fetch_text(files["totals"])), None, "totals"
            for rank, row in enumerate(sorted(rows, key=lambda x: -x["points"]), start=1):
                out.append({"season": end_year, "award": award, "rank": rank,
                            "source": source, "ballots": n_ballots, **row})
            top = max(rows, key=lambda x: x["points"]) if rows else {}
            print(season, award, source, n_ballots, len(rows), "cands; winner", top.get("name"), top.get("points"), flush=True)
            time.sleep(1)
    df = pd.DataFrame(out)
    df.to_csv(ROOT / "data" / "raw" / "awards.csv", index=False)
    print("saved", len(df))


if __name__ == "__main__":
    main()
