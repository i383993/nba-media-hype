"""NBA team names across data sources.

Keys are nba_api abbreviations. `yahoo` matches data/raw/odds_yahoo, `query`
is the GDELT search phrase (full name to avoid "Heat"/"Magic"/"Jazz" noise).
"""

TEAMS = {
    "ATL": {"yahoo": "Atlanta", "query": '"Atlanta Hawks"'},
    "BOS": {"yahoo": "Boston", "query": '"Boston Celtics"'},
    "BKN": {"yahoo": "Brooklyn", "query": '"Brooklyn Nets"'},
    "CHA": {"yahoo": "Charlotte", "query": '"Charlotte Hornets"'},
    "CHI": {"yahoo": "Chicago", "query": '"Chicago Bulls"'},
    "CLE": {"yahoo": "Cleveland", "query": '"Cleveland Cavaliers"'},
    "DAL": {"yahoo": "Dallas", "query": '"Dallas Mavericks"'},
    "DEN": {"yahoo": "Denver", "query": '"Denver Nuggets"'},
    "DET": {"yahoo": "Detroit", "query": '"Detroit Pistons"'},
    "GSW": {"yahoo": "Golden State", "query": '"Golden State Warriors"'},
    "HOU": {"yahoo": "Houston", "query": '"Houston Rockets"'},
    "IND": {"yahoo": "Indiana", "query": '"Indiana Pacers"'},
    "LAC": {"yahoo": "LA Clippers", "query": '"Los Angeles Clippers"'},
    "LAL": {"yahoo": "LA Lakers", "query": '"Los Angeles Lakers"'},
    "MEM": {"yahoo": "Memphis", "query": '"Memphis Grizzlies"'},
    "MIA": {"yahoo": "Miami", "query": '"Miami Heat"'},
    "MIL": {"yahoo": "Milwaukee", "query": '"Milwaukee Bucks"'},
    "MIN": {"yahoo": "Minnesota", "query": '"Minnesota Timberwolves"'},
    "NOP": {"yahoo": "New Orleans", "query": '"New Orleans Pelicans"'},
    "NYK": {"yahoo": "New York", "query": '"New York Knicks"'},
    "OKC": {"yahoo": "Oklahoma City", "query": '"Oklahoma City Thunder"'},
    "ORL": {"yahoo": "Orlando", "query": '"Orlando Magic"'},
    "PHI": {"yahoo": "Philadelphia", "query": '"Philadelphia 76ers"'},
    "PHX": {"yahoo": "Phoenix", "query": '"Phoenix Suns"'},
    "POR": {"yahoo": "Portland", "query": '"Portland Trail Blazers"'},
    "SAC": {"yahoo": "Sacramento", "query": '"Sacramento Kings"'},
    "SAS": {"yahoo": "San Antonio", "query": '"San Antonio Spurs"'},
    "TOR": {"yahoo": "Toronto", "query": '"Toronto Raptors"'},
    "UTA": {"yahoo": "Utah", "query": '"Utah Jazz"'},
    "WAS": {"yahoo": "Washington", "query": '"Washington Wizards"'},
}

YAHOO_TO_ABBR = {v["yahoo"]: k for k, v in TEAMS.items()}
