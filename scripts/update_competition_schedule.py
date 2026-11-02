#!/usr/bin/env python3
"""Collect 2026/27 cup fixtures/results without modifying EPL predictions.

Source: https://github.com/oladeeayo/open-matchday
Run: python scripts/update_competition_schedule.py
"""
import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/data/competition_schedule.json"
HISTORY = ROOT / "docs/data/competition_results_archive.json"
BASE = "https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data"
SEASON = "2627"
COMPETITIONS = {
    "UCL": "UEFA_1_champions-league",
    "UEL": "UEFA_1_europa-league",
    "UECL": "UEFA_1_conference-league",
    "FAC": "ENG_CUP_fa-cup",
    "EFL": "ENG_CUP_efl-cup",
}
# Only explicitly reviewed spellings are matched to EPL teams.
EPL = {
    "Arsenal", "Aston Villa", "Bournemouth", "Brentford", "Brighton",
    "Chelsea", "Coventry", "Crystal Palace", "Everton", "Fulham",
    "Hull", "Leeds", "Liverpool", "Man City", "Man United",
    "Newcastle", "Nottingham", "Sunderland", "Tottenham", "West Ham",
}
ALIASES = {
    "Manchester City": "Man City", "Man Utd": "Man United",
    "Manchester United": "Man United", "Newcastle United": "Newcastle",
    "AFC Bournemouth": "Bournemouth", "Brighton & Hove Albion": "Brighton",
    "Brighton and Hove Albion": "Brighton", "Nottingham Forest": "Nottingham",
    "Nottingham Forest FC": "Nottingham", "Tottenham Hotspur": "Tottenham",
    "West Ham United": "West Ham", "Leeds United": "Leeds",
    "Coventry City": "Coventry", "Hull City": "Hull",
    "Sunderland AFC": "Sunderland", "Arsenal FC": "Arsenal",
    "Chelsea FC": "Chelsea", "Liverpool FC": "Liverpool",
    "Fulham FC": "Fulham", "Everton FC": "Everton",
    "Brentford FC": "Brentford", "Crystal Palace FC": "Crystal Palace",
    "Aston Villa FC": "Aston Villa",
}
def canon(name):
    value = name.strip()
    return ALIASES.get(value, value)

def read_csv(session, competition, kind):
    url = f"{BASE}/{competition}/{kind}_{SEASON}.csv"
    response = session.get(url, timeout=35)
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    required = {"date", "home", "away"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Empty or invalid CSV: {url}")
    return rows, url

def valid_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()

def build_match(competition, kind, row):
    date = valid_date(row["date"])
    home_raw, away_raw = row["home"].strip(), row["away"].strip()
    if not home_raw or not away_raw:
        raise ValueError(f"Missing team in {competition} {date}")
    home, away = canon(home_raw), canon(away_raw)
    # Stable identity does not depend on the mutable kickoff time.
    key = f"{competition}|{date}|{home_raw}|{away_raw}"
    result = {
        "id": key, "competition": competition, "date": date,
        "timeSource": row.get("time", "").strip(), "timeVerifiedUTC": None,
        "home": home, "away": away,
        "homeRaw": home_raw, "awayRaw": away_raw,
        "homeEpl": home in EPL, "awayEpl": away in EPL,
        "status": "FINISHED" if kind == "results" else "SCHEDULED",
        "source": "open-matchday",
    }
    if kind == "results":
        result["score"] = {
            "home": int(row["ft_home"]), "away": int(row["ft_away"])
        }
        result["upstreamSource"] = row.get("source", "")
    return result

def load_history():
    if not HISTORY.exists():
        return {"version": 1, "matches": {}, "changes": []}
    return json.loads(HISTORY.read_text(encoding="utf-8"))

def main():
    session = requests.Session()
    all_matches, coverage = [], {}
    # All sources must validate before either output is touched.
    for code, directory in COMPETITIONS.items():
        rows = []
        for kind in ("results", "fixtures"):
            raw, url = read_csv(session, directory, kind)
            matches = [build_match(code, kind, row) for row in raw]
            rows.extend(matches)
            coverage[f"{code}_{kind}"] = {"count": len(matches), "url": url}
        all_matches.extend(rows)
    ids = [m["id"] for m in all_matches]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate competition/date/team identity; manual review required")
    relevant = sorted(
        [m for m in all_matches if m["homeEpl"] or m["awayEpl"]],
        key=lambda m: (m["date"], m["competition"], m["home"]),
    )
    history = load_history()
    now = datetime.now(timezone.utc).isoformat()
    for m in all_matches:
        if m["status"] != "FINISHED":
            continue
        old = history["matches"].get(m["id"])
        if old is None:
            history["matches"][m["id"]] = dict(m, firstSeenAt=now)
        elif old.get("score") != m.get("score"):
            history["changes"].append({
                "id": m["id"], "detectedAt": now,
                "previous": old.get("score"), "incoming": m.get("score"),
            })
            # Preserve original archived result until a correction is reviewed.
    schedule = {
        "version": 1, "season": "2026/27", "updatedAt": now,
        "source": "https://github.com/oladeeayo/open-matchday",
        "notice": "Unverified source kickoff times are not used for hour-level rest calculations.",
        "coverage": coverage, "matches": relevant,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schedule, ensure_ascii=False, indent=2), encoding="utf-8")
    HISTORY.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Competition schedule: {len(relevant)} EPL-team matches; archived results: {len(history['matches'])}")
if __name__ == "__main__":
    main()
