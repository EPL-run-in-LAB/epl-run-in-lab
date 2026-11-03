#!/usr/bin/env python3
"""Integrate pinned CC0 UEFA tournament results with the independent league warehouse.

Read-only source: data/history/uefa/raw/{season}/{cl,el,conf}.txt.
The two missing 2025/26 UEL and UECL main-phase files stay explicitly missing.
Regular-time, extra-time, shootout and cancelled matches are NEVER conflated.
The production prediction pipeline is not imported, mutated or retrained.
"""
import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from datetime import date
from pathlib import Path
from build_history_warehouse import ROOT, register_club, DB

MANIFEST = ROOT / "data/history/uefa/manifest.json"
REPORT = ROOT / "data/history/uefa_validation_report.json"
CODES = {"UCL": "cl", "UEL": "el", "UECL": "conf"}
COUNTRY_MAP = {"GER": "DE", "ESP": "ES", "ITA": "IT", "FRA": "FR", "MCO": "FR"}
MONTHS = {v:i for i,v in enumerate(("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"),1)}
DATE_RE = re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Za-z]{3})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
MATCH_RE = re.compile(
    r"^(?:(?P<time>\d{1,2}:\d{2})\s+)?"
    r"(?P<home>.+?)\s+\((?P<home_country>[A-Z]{2,3})\)\s+v\s+"
    r"(?P<away>.+?)\s+\((?P<away_country>[A-Z]{2,3})\)\s+"
    r"(?P<result>.+)$"
)
AET_RE = re.compile(r"(\d+)-(\d+)\s+a\.e\.t\.", re.I)
PEN_RE = re.compile(r"(\d+)-(\d+)\s+pen\.", re.I)
FIRST_PERIOD_RE = re.compile(r"\((\d+)-(\d+)(?:,\s*\d+-\d+)?\)")
NORMAL_RE = re.compile(r"^(\d+)-(\d+)(?:\b|$)")
HEADER_COUNT_RE = re.compile(r"^# Matches\s+(\d+)\s*$", re.M)

UEFA_SCHEMA = """
CREATE TABLE IF NOT EXISTS uefa_matches (
 match_id TEXT PRIMARY KEY,
 season_id TEXT NOT NULL REFERENCES seasons(season_id),
 match_date TEXT NOT NULL,
 stage TEXT NOT NULL,
 kickoff_source TEXT,
 home_club_id TEXT NOT NULL REFERENCES clubs(club_id),
 away_club_id TEXT NOT NULL REFERENCES clubs(club_id),
 home_raw TEXT NOT NULL, away_raw TEXT NOT NULL,
 home_goals_90 INTEGER CHECK(home_goals_90 >= 0),
 away_goals_90 INTEGER CHECK(away_goals_90 >= 0),
 home_goals_aet INTEGER CHECK(home_goals_aet >= 0),
 away_goals_aet INTEGER CHECK(away_goals_aet >= 0),
 home_penalties INTEGER CHECK(home_penalties >= 0),
 away_penalties INTEGER CHECK(away_penalties >= 0),
 status TEXT NOT NULL CHECK(status IN ('FINISHED', 'CANCELLED')),
 score_text TEXT NOT NULL,
 source_line INTEGER NOT NULL,
 UNIQUE(season_id, match_date, home_club_id, away_club_id)
);
CREATE INDEX IF NOT EXISTS idx_uefa_match_date ON uefa_matches(match_date);
CREATE INDEX IF NOT EXISTS idx_uefa_home ON uefa_matches(home_club_id,match_date);
CREATE INDEX IF NOT EXISTS idx_uefa_away ON uefa_matches(away_club_id,match_date);
"""

def parse_result(value):
    value = value.strip()
    if value.lower() in ("[cancelled]", "[canceled]"):
        return {"status":"CANCELLED", "regulation":None, "afterExtra":None, "penalties":None}
    extra = AET_RE.search(value)
    pens = PEN_RE.search(value)
    if extra:
        # On source lines with AET, the FIRST bracketed score is 90-minute
        # regulation. The preceding 'a.e.t.' score is the 120-minute score.
        base = FIRST_PERIOD_RE.search(value)
        if not base:
            raise ValueError("Unknown AET score notation (quarantined): " + value)
        regulation = [int(base.group(1)), int(base.group(2))]
        extra_score = [int(extra.group(1)), int(extra.group(2))]
    elif not pens:
        first = NORMAL_RE.match(value)
        if not first:
            raise ValueError("Unrecognised score notation (quarantined): " + value)
        regulation = [int(first.group(1)), int(first.group(2))]
        extra_score = None
    else:
        raise ValueError("Penalty score without extra-time notation: " + value)
    penalty_score = [int(pens.group(1)), int(pens.group(2))] if pens else None
    return {"status":"FINISHED", "regulation":regulation,
            "afterExtra":extra_score, "penalties":penalty_score}

def parse_football_txt(text, season, competition):
    declared = HEADER_COUNT_RE.search(text)
    if not declared:
        raise ValueError("Missing official source header count: " + competition + season)
    source_count = int(declared.group(1))
    matches = []
    stage = "UNKNOWN"
    current_date = None
    first_year = int(season.split("-")[0])
    for line_no, original in enumerate(text.splitlines(), 1):
        line = original.strip()
        if not line or line.startswith(("#", "=")):
            continue
        if line.startswith("▪"):
            stage = line.lstrip("▪").strip()
            continue
        day = DATE_RE.fullmatch(line)
        if day:
            mon = MONTHS.get(day.group(1).title())
            if mon is None:
                raise ValueError("Unknown month " + repr(line))
            year = int(day.group(3)) if day.group(3) else (first_year if mon >= 8 else first_year + 1)
            current_date = date(year, mon, int(day.group(2))).isoformat()
            continue
        if not re.search(r"\sv\s",line):
            continue
        m = MATCH_RE.fullmatch(line)
        if not m:
            raise ValueError("Unparsed possible match at line " + str(line_no) + ": " + line)
        if not current_date:
            raise ValueError("Match without a date at line " + str(line_no))
        if stage == "UNKNOWN":
            raise ValueError("Match without a competition stage at line " + str(line_no))
        home, away = m.group("home").strip(), m.group("away").strip()
        if home == away and m.group("home_country") == m.group("away_country"):
            raise ValueError("Identical opponents: " + line)
        score = parse_result(m.group("result"))
        matches.append({
            "line": line_no, "date": current_date, "stage": stage,
            "time": m.group("time"), "home": home, "away": away,
            "home_country": m.group("home_country"), "away_country":m.group("away_country"),
            "score_text":m.group("result").strip(), **score
        })
    if len(matches) != source_count:
        raise ValueError("Source header/match count mismatch for " + competition + " " +
                         season + ": " + str(source_count) + " vs " + str(len(matches)))
    return matches

def source_key(competition, season, match):
    # Completed historical matches only. A confirmed live provider fixture ID
    # will be required before this scheme is ever used for live rescheduling.
    items = [competition, season, match["date"], match["stage"],
             match["home_country"], match["home"], match["away_country"], match["away"]]
    return "uefa-" + hashlib.sha256("\0".join(items).encode()).hexdigest()[:28]

def append_uefa(db_path=DB, manifest_path=MANIFEST, report_path=REPORT):
    db_path, manifest_path, report_path = map(Path, (db_path, manifest_path, report_path))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("license") != "CC0-1.0" or not re.fullmatch(
            "[a-f0-9]{40}",manifest.get("sourceCommit","")):
        raise ValueError("Unreviewed license or non-pinned UEFA source")
    sources = manifest["available"]
    if len(sources) != 13 or len(manifest.get("missing",[])) != 2:
        raise ValueError("Expected 13 known sources and 2 explicitly missing competition-seasons")
    expected = {(y,c) for y in ("2021-22","2022-23","2023-24","2024-25") for c in CODES}
    expected.add(("2025-26","UCL"))
    if {(x["season"],x["competition"]) for x in sources} != expected:
        raise ValueError("UEFA season coverage manifest mismatch")
    if {(x["season"],x["competition"]) for x in manifest["missing"]} != {
            ("2025-26","UEL"), ("2025-26","UECL")}:
        raise ValueError("Unexpected UEFA missing-source set")

    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")
    stats=Counter()
    by_season={}
    linked = set()
    unresolved_cross_league=set()
    originally_domestic = set(r[0] for r in con.execute("SELECT club_id FROM clubs"))
    try:
        with con:
            con.executescript(UEFA_SCHEMA)
            for cid, title in [("UCL","UEFA Champions League"),
                               ("UEL","UEFA Europa League"),
                               ("UECL","UEFA Conference League")]:
                con.execute("INSERT OR IGNORE INTO competitions VALUES (?,?,?)", (cid,"UEFA",title))
            for info in sorted(sources,key=lambda x:(x["season"], x["competition"])):
                competition, season = info["competition"],info["season"]
                path = manifest_path.parent / info["path"]
                text = path.read_text(encoding="utf-8")
                parsed = parse_football_txt(text, season, competition)
                if len(parsed) != info["declaredRows"]:
                    raise ValueError("Manifest/source count changed for " + str(path))
                season_id=competition+"|"+season
                src_url=("https://raw.githubusercontent.com/openfootball/champions-league/"
                         +manifest["sourceCommit"]+"/"+season+"/"+CODES[competition]+".txt")
                con.execute("INSERT INTO seasons VALUES (?,?,?,?,?,?,?)",
                    (season_id,competition,season,"openfootball/champions-league",
                     "CC0-1.0",manifest["sourceCommit"],src_url))
                subtotal=Counter()
                for m in parsed:
                    home_c=COUNTRY_MAP.get(m["home_country"],m["home_country"])
                    away_c=COUNTRY_MAP.get(m["away_country"],m["away_country"])
                    home=register_club(con,home_c,m["home"],source_project="openfootball/champions-league")
                    away=register_club(con,away_c,m["away"],source_project="openfootball/champions-league")
                    if home == away:
                        raise ValueError("Same club identity on two sides: " + repr(m))
                    for cid in [home,away]:
                        if cid in originally_domestic:
                            linked.add(cid)
                    for country,raw,cid in [(home_c,m["home"],home),(away_c,m["away"],away)]:
                        if country in ("DE","ES","IT","FR") and cid not in originally_domestic:
                            unresolved_cross_league.add((country,raw,cid))
                    score90=m["regulation"]
                    extra=m["afterExtra"]
                    penalties=m["penalties"]
                    con.execute("""INSERT INTO uefa_matches
                        (match_id,season_id,match_date,stage,kickoff_source,
                         home_club_id,away_club_id,home_raw,away_raw,
                         home_goals_90,away_goals_90,home_goals_aet,away_goals_aet,
                         home_penalties,away_penalties,status,score_text,source_line)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (source_key(competition,season,m),season_id,m["date"],m["stage"],m["time"],
                         home,away,m["home"],m["away"],
                         *(score90 if score90 is not None else (None,None)),
                         *(extra if extra is not None else (None,None)),
                         *(penalties if penalties is not None else (None,None)),
                         m["status"],m["score_text"],m["line"]))
                    subtotal["rows"]+=1
                    subtotal["finished" if m["status"]=="FINISHED" else "cancelled"]+=1
                    if extra: subtotal["extra_time"]+=1
                    if penalties: subtotal["penalties"]+=1
                stats.update(subtotal)
                by_season[season_id]=dict(subtotal)
            con.execute("DROP VIEW IF EXISTS v_all_matches")
            con.execute("""CREATE VIEW v_all_matches AS
                SELECT match_id,season_id,match_date,home_club_id,away_club_id,
                       home_goals AS home_goals_90,away_goals AS away_goals_90,
                       status,model_training_eligible AS regulation_training_eligible
                FROM matches
                UNION ALL
                SELECT match_id,season_id,match_date,home_club_id,away_club_id,
                       home_goals_90,away_goals_90,status,
                       CASE WHEN status='FINISHED' THEN 1 ELSE 0 END
                FROM uefa_matches""")
            fkeys=con.execute("PRAGMA foreign_key_check").fetchall()
            if fkeys: raise ValueError("Foreign key check failed: "+repr(fkeys[:10]))
            if stats["rows"] != 1941 or stats["finished"] != 1939 or stats["cancelled"] != 2:
                raise ValueError("Unexpected UEFA game coverage: "+repr(dict(stats)))
            if not linked:
                raise ValueError("No UEFA clubs were linked to domestic records")
            full_count=con.execute("SELECT COUNT(*) FROM v_all_matches").fetchone()[0]
            if full_count != 8949: raise ValueError("Unexpected unified row count: "+str(full_count))
            club_count=con.execute("SELECT COUNT(*) FROM clubs").fetchone()[0]
            report={
                "schemaVersion":1,"sourceRepository":manifest["sourceRepository"],
                "sourceCommit":manifest["sourceCommit"],"license":manifest["license"],
                "totals":dict(stats),"bySeason":by_season,"allMatchRows":full_count,
                "totalDistinctClubs":club_count,"linkedDomesticClubs":len(linked),
                "linkedDomesticClubIds":sorted(linked),
                "potentialUnmatchedDomesticAliases":[{
                    "country":c,"rawName":n,"assignedClubId":cid
                    } for c,n,cid in sorted(unresolved_cross_league)],
                "missingCompetitionSeasons":manifest["missing"],
                "metricPolicy":"90-minute goals kept separate from AET/penalties. Cancellations never included in model.",
                "identityPolicy":"Reviewed alias table only. Country tags distinguish clubs; no fuzzy joins.",
                "dataPolicy":"No current non-commercial feeds or existing prediction model files imported."
            }
        report_path.parent.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return report
    finally:
        con.close()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--db",type=Path,default=DB)
    ap.add_argument("--manifest",type=Path,default=MANIFEST)
    ap.add_argument("--report",type=Path,default=REPORT)
    a=ap.parse_args()
    result=append_uefa(db_path=a.db,manifest_path=a.manifest,report_path=a.report)
    print("Integrated UEFA",result["totals"],"matched domestic club IDs:",result["linkedDomesticClubs"])

if __name__=="__main__":
    main()
