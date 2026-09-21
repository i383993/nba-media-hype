"""Count ASAP Sports transcripts per sport and event for a given year.

Walks year page -> event pages -> event-day pages and counts unique
interview links. Writes data/coverage_<year>.csv (one row per event).
"""
import csv
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

BASE = "https://www.asapsports.com/"
HEADERS = {"User-Agent": "Mozilla/5.0 (academic research; sloan-interviews)"}
CATEGORIES = {
    1: "Football", 2: "Baseball", 3: "Auto Racing", 4: "Golf", 5: "Hockey",
    7: "Tennis", 11: "Basketball", 13: "Boxing", 14: "Soccer", 22: "Cricket",
}

session = requests.Session()
session.headers.update(HEADERS)


def get(url):
    for attempt in range(3):
        try:
            time.sleep(0.25)
            r = session.get(url, timeout=30)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    return ""


def event_links(cat, year):
    html = get(f"{BASE}show_year.php?category={cat}&year={year}")
    links = re.findall(r'href="([^"]*show_events\.php\?[^"]+)"', html)
    return list(dict.fromkeys(links))


def count_event(url):
    html = get(url)
    days = list(dict.fromkeys(re.findall(r'href="([^"]*show_event\.php\?event_id=[^"]+)"', html)))
    ids = set(re.findall(r"show_interview\.php\?id=(\d+)", html))
    for day in days:
        ids |= set(re.findall(r"show_interview\.php\?id=(\d+)", get(day.replace("&amp;", "&"))))
    return len(days), len(ids)


def main(year):
    out = Path(__file__).resolve().parent.parent / "data" / f"coverage_{year}.csv"
    out.parent.mkdir(exist_ok=True)
    rows = []
    for cat, sport in CATEGORIES.items():
        events = event_links(cat, year)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda u: count_event(u.replace("&amp;", "&")), events))
        for url, (days, n) in zip(events, results):
            title = requests.utils.unquote(re.search(r"title=([^&]*)", url).group(1)).replace("+", " ")
            rows.append({"year": year, "category": cat, "sport": sport, "event": title,
                         "days": days, "transcripts": n, "url": url})
        print(f"{sport:12s} events={len(events):4d} transcripts={sum(r[1] for r in results):6d}", flush=True)
    with out.open("w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2025)
