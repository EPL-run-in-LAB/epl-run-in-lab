#!/usr/bin/env python3
"""2026/27 multi-competition STAGING. Never touches EPL prediction inputs.

CC0 OpenFootball supplies full-league reference fixtures. Existing non-commercial
open-matchday supplies current results and UEFA/domestic cups. All mismatches,
unknown club identities, date-only timing and licensing limits are retained.
"""
import argparse
import csv
import hashlib
import io
import json
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
ALIAS=ROOT/"data/live/club_aliases_2627.json"
OUT=ROOT/"data/live/current_schedule_2627.json"
REPORT=ROOT/"data/live/quality_report_2627.json"
OF="https://raw.githubusercontent.com/openfootball/football.json/master/2026-27"
OM="https://raw.githubusercontent.com/oladeeayo/open-matchday/master/data"
LEAGUES={"EN1":("en.1","ENG_1_premier-league",380),
 "DE1":("de.1","GER_1_bundesliga",306),
 "ES1":("es.1","ESP_1_la-liga",380),
 "IT1":("it.1","ITA_1_serie-a",380),
 "FR1":("fr.1","FRA_1_ligue-1",306),
 "EN2":("en.2","ENG_2_championship",552)}
CUPS={"UCL":"UEFA_1_champions-league",
 "UEL":"UEFA_1_europa-league",
 "UECL":"UEFA_1_conference-league",
 "FAC":"ENG_CUP_fa-cup","EFL":"ENG_CUP_efl-cup"}

def sha_id(*fields):
    return "stage-"+hashlib.sha256("\0".join(map(str,fields)).encode("utf-8")).hexdigest()[:24]

def parse_csv(data,kind):
    reader=csv.DictReader(io.StringIO(data))
    required={"gw","date","home","away"}|({"ft_home","ft_away"} if kind=="results" else set())
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Missing required columns for "+kind)
    rows=[]
    for row in reader:
        dt=date.fromisoformat(row["date"])
        if dt.year not in (2026,2027):raise ValueError("Bad year "+row["date"])
        if not row["home"] or not row["away"] or row["home"]==row["away"]:
            raise ValueError("Invalid fixture participants")
        score=[int(row["ft_home"]),int(row["ft_away"])] if kind=="results" else None
        if score is not None and min(score)<0:raise ValueError("Negative result")
        rows.append({"date":row["date"],"round":str(row["gw"]),
                     "home":row["home"].strip(),"away":row["away"].strip(),
                     "timeUnverified":row.get("time") or None,"score":score,
                     "providerOrigin":row.get("source") if kind=="results" else None})
    if not rows:raise ValueError("Empty "+kind+" CSV")
    return rows

def parse_cc0(data,expected):
    raw=data.get("matches",[])
    if len(raw)!=expected:raise ValueError("Incomplete CC0 reference, expected "+str(expected))
    out={}
    for row in raw:
        key=(row["team1"],row["team2"])
        if key in out:raise ValueError("Duplicate CC0 league home/away pairing")
        score=row.get("score")
        score=score.get("ft") if isinstance(score,dict) else score if isinstance(score,list) else None
        if score is not None and (not isinstance(score,list) or len(score)!=2 or
               any(type(s) is not int or s<0 for s in score)):
            raise ValueError("Unrecognised CC0 result")
        date.fromisoformat(row["date"])
        out[key]={"date":row["date"],"score":score}
    return out

def get_csv(session,url,kind):
    response=session.get(url,timeout=35)
    response.raise_for_status()
    return parse_csv(response.text,kind)

def build(session,aliases,reference_date,previous=None):
    date.fromisoformat(reference_date)
    if aliases.get("schemaVersion")!=1:raise ValueError("Unreviewed club alias registry")
    matches=[];stats={};date_conflicts=[];unknown=set()
    corroborated=0;supplemental=0
    previous=previous or {}
    for comp,(file,provider,total) in LEAGUES.items():
        cc0url=OF+"/"+file+".json"
        ref=session.get(cc0url,timeout=35);ref.raise_for_status()
        baseline=parse_cc0(ref.json(),total)
        observed=set();league_rows=[]
        for kind in ("results","fixtures"):
            url=OM+"/"+provider+"/"+kind+"_2627.csv"
            for row in get_csv(session,url,kind):
                h=aliases["league"][comp].get(row["home"])
                a=aliases["league"][comp].get(row["away"])
                if not h or not a:raise ValueError("Unreviewed league alias "+str((comp,row["home"],row["away"])))
                pair=(h,a)
                if pair in observed:raise ValueError("Duplicate league fixture "+str((comp,pair)))
                observed.add(pair)
                cc0=baseline.get(pair)
                if cc0 is None:raise ValueError("No matching CC0 league fixture "+str((comp,pair)))
                if cc0["score"] is not None and row["score"] is not None and cc0["score"]!=row["score"]:
                    raise ValueError("Conflicting two-source match score "+str((comp,pair)))
                confirmation=cc0["score"] is not None and row["score"] is not None
                corroborated+=int(confirmation)
                supplemental+=int(cc0["score"] is None and row["score"] is not None)
                different_date=cc0["date"]!=row["date"]
                if different_date:
                    date_conflicts.append({"competition":comp,"home":h,"away":a,
                        "cc0Date":cc0["date"],"stagingDate":row["date"]})
                status="FINISHED" if row["score"] is not None else ("PAST_UNVERIFIED" if row["date"]<reference_date else "SCHEDULED")
                league_rows.append({"id":sha_id(comp,row["round"],h,a),"competition":comp,
                    "season":"2026-27","round":row["round"],"date":row["date"],
                    "home":row["home"],"away":row["away"],
                    "homeClubId":aliases["canonicalId"][comp+"|"+h],
                    "awayClubId":aliases["canonicalId"][comp+"|"+a],
                    "status":status,"score":row["score"],"scoreCrossVerifiedCC0":confirmation,
                    "cc0Date":cc0["date"],"dateDisagreement":different_date,
                    "timeUnverified":row["timeUnverified"],"kickoffUTC":None,
                    "source":"open-matchday","sourceLicense":"noncommercial",
                    "sourceRowOrigin":row["providerOrigin"],
                    "cc0ReferenceURL":cc0url})
        if len(league_rows)!=total:raise ValueError("Not all league fixtures represented: "+comp)
        stats[comp]={"total":total,"finished":sum(x["status"]=="FINISHED" for x in league_rows),
            "future":sum(x["status"]=="SCHEDULED" for x in league_rows),
            "pastWithoutResult":sum(x["status"]=="PAST_UNVERIFIED" for x in league_rows),
            "cc0Scored":sum(x["score"] is not None for x in baseline.values()),
            "dateDisagreements":sum(x["dateDisagreement"] for x in league_rows)}
        matches.extend(league_rows)
    for comp,folder in CUPS.items():
        cup=[];seen=set()
        for kind in ("results","fixtures"):
            for row in get_csv(session,OM+"/"+folder+"/"+kind+"_2627.csv",kind):
                h=aliases["other"].get(row["home"])
                a=aliases["other"].get(row["away"])
                if not h:unknown.add(row["home"])
                if not a:unknown.add(row["away"])
                identity=(comp,row["round"],row["date"],row["home"],row["away"])
                if identity in seen:raise ValueError("Duplicate cup observation "+str(identity))
                seen.add(identity)
                # No immutable source match ID; date changes are new observations,
                # not an invitation to merge two potentially distinct cup games.
                status="FINISHED" if row["score"] is not None else ("PAST_UNVERIFIED" if row["date"]<reference_date else "SCHEDULED")
                cup.append({"id":sha_id(*identity),"competition":comp,"season":"2026-27",
                    "round":row["round"],"date":row["date"],
                    "home":row["home"],"away":row["away"],"homeClubId":h,"awayClubId":a,
                    "identityResolved":bool(h and a),"status":status,"score":row["score"],
                    "timeUnverified":row["timeUnverified"],"kickoffUTC":None,
                    "source":"open-matchday","sourceLicense":"noncommercial",
                    "sourceRowOrigin":row["providerOrigin"]})
        stats[comp]={"total":len(cup),"finished":sum(x["status"]=="FINISHED" for x in cup),
           "future":sum(x["status"]=="SCHEDULED" for x in cup),
           "pastWithoutResult":sum(x["status"]=="PAST_UNVERIFIED" for x in cup),
           "unknownClubFixtures":sum(not x["identityResolved"] for x in cup)}
        matches.extend(cup)
    if len({x["id"] for x in matches})!=len(matches):
        raise ValueError("Duplicate generated match identifiers")
    if sum(stats[c]["total"] for c in LEAGUES)!=2304 or any(stats[c]["total"]==0 for c in CUPS):
        raise ValueError("Insufficient source schedule coverage")
    # Never silently remove results collected on an earlier run.
    for comp,row in stats.items():
        old=previous.get("coverage",{}).get(comp,{})
        if row["finished"]<old.get("finished",0):
            raise ValueError("Upstream result coverage regressed: "+comp)
    at=datetime.now(timezone.utc).isoformat()
    data={"schemaVersion":1,"season":"2026-27","generatedAt":at,
          "asOfDate":reference_date,"status":"STAGING_NOT_MODEL_INPUT",
          "licenseNote":"Current fixture source is non-commercial; not cleared for ad monetization.",
          "timePolicy":"Unverified local time stays textual; UTC kickoff and travel/rest hours are never invented.",
          "matches":sorted(matches,key=lambda x:(x["date"],x["competition"],x["home"],x["away"]))}
    report={"schemaVersion":1,"season":"2026-27","generatedAt":at,
            "coverage":stats,"matchTotal":len(matches),
            "cc0ScoreAgreementCount":corroborated,
            "supplementaryResultsMissingFromCC0":supplemental,
            "dateDisagreements":date_conflicts,
            "unknownOpponentNames":sorted(unknown),
            "historicalUEFAGaps":[{"season":"2025-26","competition":c,"status":"unresolved-source-rights"} for c in ("UEL","UECL")],
            "warnings":["OpenFootball scores lag current fixtures in some leagues.",
                        "Current results beyond CC0 are provisional, from a noncommercial dataset.",
                        "Dates with conflicts are flagged and may not be used for verified rest intervals.",
                        "Unknown non-top-five teams must not be interpreted as having no domestic fixtures.",
                        "There are no verified UTC kickoff times in this dataset.",
                        "2025/26 missing UEFA competition files have not been silently fabricated."]}
    return data,report

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--aliases",type=Path,default=ALIAS)
    ap.add_argument("--out",type=Path,default=OUT)
    ap.add_argument("--report",type=Path,default=REPORT)
    ap.add_argument("--reference-date",default=date.today().isoformat())
    args=ap.parse_args()
    aliases=json.loads(args.aliases.read_text(encoding="utf-8"))
    previous=json.loads(args.report.read_text(encoding="utf-8")) if args.report.exists() else None
    with requests.Session() as s:
        data,report=build(s,aliases,args.reference_date,previous)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    args.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("2026-27 staging:",report["matchTotal"],"fixtures,",
          report["supplementaryResultsMissingFromCC0"],"additional results,",
          len(report["dateDisagreements"]),"date disagreements")
if __name__=="__main__":main()
