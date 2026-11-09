#!/usr/bin/env python3
"""UEFA two-sided schedule context from the 2026/27 staging feed.

Calendar dates are only provisional, never verified UTC or estimated travel.
For clubs without a complete domestic fixture list, missing games are UNKNOWN,
not zero. Does not feed the EPL prediction model.
"""
import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/live/current_schedule_2627.json"
OUTPUT=ROOT/"data/live/uefa_rest_context_2627.json"
EXTENDED=ROOT/"data/live/extended_domestic_2627.json"
DOMESTIC={"EN1","EN2","DE1","ES1","IT1","FR1","NL1","PT1"}
UEFA={"UCL","UEL","UECL"}

def context_for(match,club_id,index,domestic_clubs):
    if not club_id:
        return {"clubId":None,"domesticScheduleAvailable":False,"calendarRestDays":None,
                "reason":"UNRESOLVED_CLUB_ID"}
    if club_id not in domestic_clubs:
        return {"clubId":club_id,"domesticScheduleAvailable":False,
                "calendarRestDays":None,"reason":"DOMESTIC_SCHEDULE_NOT_COLLECTED"}
    same_team=[r for r in index[club_id] if r["date"]<match["date"]]
    previous=max(same_team,key=lambda x:(x["date"],x["id"])) if same_team else None
    recent=[r for r in same_team if 0<(date.fromisoformat(match["date"])-date.fromisoformat(r["date"])).days<=7]
    if not previous:
        return {"clubId":club_id,"domesticScheduleAvailable":True,
                "calendarRestDays":None,"previousMatch":None,"matchesPrevious7Days":len(recent),
                "reason":"NO_EARLIER_OBSERVATION"}
    disputed=bool(previous.get("dateDisagreement") or match.get("dateDisagreement"))
    days=(date.fromisoformat(match["date"])-date.fromisoformat(previous["date"])).days-1
    return {"clubId":club_id,"domesticScheduleAvailable":True,
            "calendarRestDays":None if disputed else days,
            "previousMatch":{"date":previous["date"],"competition":previous["competition"],
                             "status":previous["status"],"id":previous["id"],
                             "dateDisagreement":bool(previous.get("dateDisagreement",False))},
            "matchesPrevious7Days":len(recent),
            "reason":"CONFLICTED_DATE" if disputed else "PROVISIONAL_DATE_ONLY",
            "verifiedKickoffGapHours":None}

def build(data):
    if data.get("status")!="STAGING_NOT_MODEL_INPUT" or data.get("season")!="2026-27":
        raise ValueError("Not the isolated 2026/27 staging feed")
    matches=list(data["matches"])
    # The optional NL/PT feed is included only after a whole-league completeness gate.
    if EXTENDED.exists():
        extra=json.loads(EXTENDED.read_text(encoding="utf-8"))
        if extra.get("season")!="2026-27" or extra.get("status")!="STAGING_NOT_MODEL_INPUT":
            raise ValueError("Invalid external league staging")
        allowed={k for k,v in extra.get("coverage",{}).items()
                 if v.get("status")=="COMPLETE_SOURCE_UNVERIFIED_DATES"}
        extended=[m for m in extra.get("matches",[]) if m.get("competition") in allowed]
        # Only exact, unambiguous same-provider club spellings may bridge UEFA and NL/PT.
        # Never overwrite an independently reviewed ID or perform fuzzy matching.
        from collections import defaultdict as _dd
        ids_by_name=_dd(set)
        for row in extended:
            for side in ("home", "away"):
                if row.get(side+"ClubId"):
                    ids_by_name[row[side]].add(row[side+"ClubId"])
        unique_ids={name:next(iter(ids)) for name,ids in ids_by_name.items() if len(ids)==1}
        for row in matches:
            if row.get("competition") not in UEFA:continue
            for side in ("home", "away"):
                if not row.get(side+"ClubId") and row.get(side) in unique_ids:
                    row[side+"ClubId"]=unique_ids[row[side]]
                    row[side+"IdentityBasis"]="EXACT_NAME_SAME_PROVIDER_PROVISIONAL"
        matches.extend(extended)
    domestic={id for m in matches if m["competition"] in DOMESTIC
              for id in (m.get("homeClubId"),m.get("awayClubId")) if id}
    index=defaultdict(list)
    for m in matches:
        for club in (m.get("homeClubId"),m.get("awayClubId")):
            if club:index[club].append(m)
    result=[];covered=0;partial=0;unavailable=0
    for m in matches:
        if m["competition"] not in UEFA:continue
        h=context_for(m,m.get("homeClubId"),index,domestic)
        a=context_for(m,m.get("awayClubId"),index,domestic)
        if h["domesticScheduleAvailable"] and a["domesticScheduleAvailable"]:covered+=1
        elif h["domesticScheduleAvailable"] or a["domesticScheduleAvailable"]:partial+=1
        else:unavailable+=1
        result.append({"id":m["id"],"date":m["date"],"competition":m["competition"],
            "home":m["home"],"away":m["away"],"score":m.get("score"),"status":m["status"],
            "homeSchedule":h,"awaySchedule":a})
    if len(result)!=sum(m["competition"] in UEFA for m in matches):
        raise AssertionError("UEFA source coverage changed")
    return {"schemaVersion":1,"season":"2026-27","source":"noncommercial provisional 2026/27 staging",
        "verifiedTravelDistances":False,"verifiedKickoffHours":False,
        "scope":"All scheduled UCL/UEL/UECL games; date-only context, not causal fatigue",
        "coverage":{"uefaFixtures":len(result),"bothDomesticSchedules":covered,
                    "oneDomesticSchedule":partial,"neitherDomesticSchedule":unavailable},
        "notes":["A missing domestic league is NOT zero games or complete rest.",
                 "Date differences across sources invalidate trusted rest calculations.",
                 "Calendar rest calculations are provisional and not inputs to predictions.",
                 "Upcoming competition dates and results may be updated by their owners."],
        "fixtures":result}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=SOURCE)
    p.add_argument("--out",type=Path,default=OUTPUT)
    args=p.parse_args()
    data=build(json.loads(args.input.read_text(encoding="utf-8")))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("UEFA schedule coverage:",data["coverage"])
if __name__=="__main__":main()
