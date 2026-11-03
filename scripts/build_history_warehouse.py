#!/usr/bin/env python3
"""Build a standalone, auditable historical football warehouse from CC0 snapshots.

Does not read or change EPL prediction inputs, archive files, or live cup schedules.
Only explicitly reviewed snapshots are included; ambiguous club aliases are not
automatically joined across competitions.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "data/history/snapshots"
DB = ROOT / "data/history/history.sqlite"
REPORT = ROOT / "data/history/validation_report.json"
SEASONS = ("2021-22", "2022-23", "2023-24", "2024-25", "2025-26")
COMPETITIONS = {
    "DE1": ("DE", "Bundesliga"),
    "ES1": ("ES", "La Liga"),
    "IT1": ("IT", "Serie A"),
    "FR1": ("FR", "Ligue 1"),
}
VALID_ORIGINS = {
    "cc0_json_ft", "cc0_json_array",
    "cc0_upstream_text", "official_decision",
}

ALIAS_FILE = ROOT / "data/history/club_alias_reviewed.json"
REVIEWED_ALIASES = json.loads(ALIAS_FILE.read_text(encoding="utf-8"))

def canonical_name(country, raw):
    """Only merge reviewed, explicit source aliases; never fuzzy-match clubs."""
    return REVIEWED_ALIASES.get(country, {}).get(raw.strip(), raw.strip())

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE competitions (
 competition_id TEXT PRIMARY KEY, country TEXT NOT NULL, name TEXT NOT NULL
);
CREATE TABLE seasons (
 season_id TEXT PRIMARY KEY,
 competition_id TEXT NOT NULL REFERENCES competitions(competition_id),
 season TEXT NOT NULL, source_project TEXT NOT NULL,
 source_license TEXT NOT NULL, source_commit TEXT NOT NULL, source_url TEXT NOT NULL,
 UNIQUE(competition_id, season)
);
CREATE TABLE clubs (
 club_id TEXT PRIMARY KEY, country TEXT NOT NULL, canonical_name TEXT NOT NULL
);
CREATE TABLE club_aliases (
 source_project TEXT NOT NULL, country TEXT NOT NULL, raw_name TEXT NOT NULL,
 club_id TEXT NOT NULL REFERENCES clubs(club_id),
 PRIMARY KEY(source_project, country, raw_name)
);
CREATE TABLE matches (
 match_id TEXT PRIMARY KEY,
 season_id TEXT NOT NULL REFERENCES seasons(season_id),
 match_date TEXT NOT NULL,
 match_round TEXT,
 home_club_id TEXT NOT NULL REFERENCES clubs(club_id),
 away_club_id TEXT NOT NULL REFERENCES clubs(club_id),
 home_raw TEXT NOT NULL, away_raw TEXT NOT NULL,
 home_goals INTEGER NOT NULL CHECK(home_goals >= 0),
 away_goals INTEGER NOT NULL CHECK(away_goals >= 0),
 status TEXT NOT NULL,
 model_training_eligible INTEGER NOT NULL CHECK(model_training_eligible IN (0, 1)),
 UNIQUE(season_id, home_club_id, away_club_id)
);
CREATE TABLE match_provenance (
 match_id TEXT PRIMARY KEY REFERENCES matches(match_id),
 score_origin TEXT NOT NULL,
 source_url TEXT NOT NULL,
 evidence_url TEXT
);
CREATE INDEX idx_matches_date ON matches(match_date);
CREATE INDEX idx_matches_home ON matches(home_club_id, match_date);
CREATE INDEX idx_matches_away ON matches(away_club_id, match_date);
"""

def club_slug(value):
    normalized = unicodedata.normalize("NFKD", value.casefold())
    ascii_value = "".join(
        c for c in normalized
        if unicodedata.category(c) != "Mn" and ord(c) < 128
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    if not slug:
        raise ValueError("Club name has no usable slug: " + value)
    return slug

def stable_match_id(competition, season, home, away):
    # The date is deliberately not part of the identity: postponements may move it.
    identity = "\0".join((competition, season, home, away)).encode("utf-8")
    return "match-" + hashlib.sha256(identity).hexdigest()[:24]

def expected_count(competition, season):
    if competition == "DE1":
        return 306
    if competition == "FR1" and season not in ("2021-22", "2022-23"):
        return 306
    return 380

def register_club(con, country, raw, source_project="openfootball/football.json"):
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Missing club name")
    name = canonical_name(country, raw)
    club_id = country.lower() + "-" + club_slug(name)
    con.execute(
        "INSERT OR IGNORE INTO clubs VALUES (?, ?, ?)",
        (club_id, country, name),
    )
    existing = con.execute(
        "SELECT club_id FROM club_aliases WHERE source_project=? AND country=? AND raw_name=?",
        (source_project, country, raw.strip()),
    ).fetchone()
    if existing is not None and existing[0] != club_id:
        raise ValueError("Conflicting reviewed club alias: " + repr((country, raw)))
    con.execute(
        "INSERT OR IGNORE INTO club_aliases VALUES (?, ?, ?, ?)",
        (source_project, country, raw.strip(), club_id),
    )
    return club_id

def build_warehouse(source_dir=SOURCES, db_path=DB, report_path=REPORT, strict=True):
    source_dir, db_path, report_path = map(Path, (source_dir, db_path, report_path))
    sources = sorted(source_dir.glob("*/*.json"))
    if strict and len(sources) != len(COMPETITIONS) * len(SEASONS):
        raise ValueError("Expected exactly twenty domestic season snapshots")
    if not sources:
        raise ValueError("No source snapshots supplied")

    db_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temp_db = db_path.with_name(db_path.name + ".new")
    temp_report = report_path.with_name(report_path.name + ".new")
    if temp_db.exists():
        temp_db.unlink()
    con = sqlite3.connect(str(temp_db))
    con.execute("PRAGMA foreign_keys=ON")
    totals = Counter()
    per_season = {}
    corrections = []
    seen_seasons = set()
    try:
        con.executescript(SCHEMA)
        for cid, (country, name) in COMPETITIONS.items():
            con.execute(
                "INSERT INTO competitions VALUES (?, ?, ?)", (cid, country, name)
            )
        for path in sources:
            doc = json.loads(path.read_text(encoding="utf-8"))
            cid, season = doc["competitionId"], doc["season"]
            if cid not in COMPETITIONS or season not in SEASONS:
                raise ValueError("Unapproved competition or season: " + str(path))
            if path.name != cid + ".json" or path.parent.name != season:
                raise ValueError("Source file name and metadata disagree: " + str(path))
            if (cid, season) in seen_seasons:
                raise ValueError("Duplicate season snapshot: " + cid + season)
            seen_seasons.add((cid, season))
            country = COMPETITIONS[cid][0]
            if doc["country"] != country:
                raise ValueError("Country mismatch: " + str(path))
            source = doc["source"]
            if source.get("license") != "CC0-1.0" or source.get("project") != "openfootball/football.json":
                raise ValueError("Unapproved license or data source: " + str(path))
            if not re.fullmatch(r"[a-f0-9]{40}", source.get("commit", "")):
                raise ValueError("Unpinned source commit: " + str(path))
            rows = doc.get("matches")
            if not isinstance(rows, list):
                raise ValueError("Missing matches: " + str(path))
            if strict and len(rows) != expected_count(cid, season):
                raise ValueError("Incorrect match count: " + cid + " " + season)
            season_id = cid + "|" + season
            con.execute(
                "INSERT INTO seasons VALUES (?, ?, ?, ?, ?, ?, ?)",
                (season_id, cid, season, source["project"], source["license"], source["commit"], source["url"]),
            )
            stats = Counter()
            for index, match in enumerate(rows):
                match_date = date.fromisoformat(match["date"])
                if not (int(season[:4]) <= match_date.year <= int(season[:4]) + 1):
                    raise ValueError("Date outside season: " + repr(match))
                home = register_club(con, country, match["home"])
                away = register_club(con, country, match["away"])
                if home == away:
                    raise ValueError("Same club on both sides: " + repr(match))
                score = match.get("score")
                if (not isinstance(score, list) or len(score) != 2 or
                        any(type(s) is not int or s < 0 for s in score)):
                    raise ValueError("Invalid or missing full-time score: " + repr(match))
                origin = match.get("origin")
                if origin not in VALID_ORIGINS:
                    raise ValueError("Unknown provenance: " + repr(match))
                status = match.get("status", "FINISHED")
                eligible = bool(match.get("modelTrainingEligible", status == "FINISHED"))
                evidence = match.get("scoreEvidence")
                if origin in ("cc0_upstream_text", "official_decision") and not evidence:
                    raise ValueError("Corrected score lacks evidence URL")
                if origin == "official_decision":
                    if status != "ABANDONED_AWARDED" or eligible:
                        raise ValueError("Officially awarded match must be flagged and excluded from model training")
                elif status != "FINISHED":
                    raise ValueError("Unexpected match status " + status)
                match_id = stable_match_id(cid, season, home, away)
                con.execute(
                    "INSERT INTO matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (match_id, season_id, match["date"], match.get("round"), home,
                     away, match["home"], match["away"], score[0], score[1],
                     status, int(eligible)),
                )
                con.execute(
                    "INSERT INTO match_provenance VALUES (?, ?, ?, ?)",
                    (match_id, origin, source["url"], evidence),
                )
                stats[origin] += 1
                if eligible:
                    stats["eligible"] += 1
                if origin in ("cc0_upstream_text", "official_decision"):
                    corrections.append({
                        "match_id": match_id, "competition": cid, "season": season,
                        "date": match["date"], "home": match["home"],
                        "away": match["away"], "score": score,
                        "origin": origin, "evidence": evidence,
                        "train_eligible": eligible,
                    })
            stats["matches"] = len(rows)
            per_season[season_id] = dict(stats)
            totals.update(stats)
        errors = con.execute("PRAGMA foreign_key_check").fetchall()
        if errors:
            raise ValueError("Foreign key violations: " + repr(errors[:5]))
        if strict and (totals["matches"] != 7008 or totals["cc0_upstream_text"] != 20 or
                       totals["cc0_json_array"] != 86 or totals["official_decision"] != 1 or
                       totals["eligible"] != 7007):
            raise ValueError("Unexpected overall coverage: " + str(dict(totals)))
        club_count = con.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
        report = {
            "schemaVersion": 1,
            "sourceScope": "CC0 historical leagues + one sourced official match adjudication",
            "competitions": len({key[0] for key in seen_seasons}),
            "seasons": len(seen_seasons),
            "clubs": club_count,
            "totals": dict(totals),
            "bySeason": per_season,
            "reviewedCorrections": corrections,
            "qualityNotes": [
                "86 direct score arrays [0,0] are correctly interpreted as actual draws.",
                "20 missing JSON results are repaired from same-project CC0 Football.TXT.",
                "Nantes-Toulouse 2026-05-17 was abandoned and awarded 0-0; exclude from 90-minute model training.",
                "Club identity only merges exact normalized country/name; cross-league alias mapping requires review.",
                "Existing prediction and cup pipelines are separate and untouched.",
            ],
        }
        con.commit()
        con.close()
        temp_report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_db.replace(db_path)
        temp_report.replace(report_path)
        return report
    except Exception:
        con.close()
        if temp_db.exists():
            temp_db.unlink()
        if temp_report.exists():
            temp_report.unlink()
        raise

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=SOURCES)
    parser.add_argument("--db", type=Path, default=DB)
    parser.add_argument("--report", type=Path, default=REPORT)
    args = parser.parse_args()
    report = build_warehouse(args.source_dir, args.db, args.report)
    print("History warehouse built:", report["totals"]["matches"],
          "fixtures,", report["totals"]["eligible"], "training-eligible")

if __name__ == "__main__":
    main()
