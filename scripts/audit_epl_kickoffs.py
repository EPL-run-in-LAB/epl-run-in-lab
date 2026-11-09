#!/usr/bin/env python3
"""Conservative third-source EPL kickoff/date reconciliation, audit-only.

football-data.org fixture IDs are scoped to its provider. They NEVER equal
Goal API fixture IDs. UTC kickoff proof is retained as an observation, not
promoted to verified hour-level rest without a second corroborated time feed.
"""
import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import requests
from update_predictions import canonical

ROOT=Path(__file__).resolve().parents[1]
STAGE=ROOT/"data/live/current_schedule_2627.json"
OUTPUT=ROOT/"data/live/epl_kickoff_crosscheck_2627.json"

def reconcile(stage, payload):
    if stage.get("season")!="2026-27" or stage.get("status")!="STAGING_NOT_MODEL_INPUT":
        raise ValueError("Invalid staging season")
    rows=[m for m in stage["matches"] if m["competition"]=="EN1"]
    indexes=defaultdict(list)
    for m in payload.get("matches",[]):
        try:
            if not m.get("utcDate") or not m.get("homeTeam") or not m.get("awayTeam"):
                continue
            h=canonical(m["homeTeam"]["name"])
            a=canonical(m["awayTeam"]["name"])
            t=datetime.fromisoformat(m["utcDate"].replace("Z","+00:00"))
            if t.tzinfo is None:continue
            loc=t.astimezone(ZoneInfo("Europe/London"))
            indexes[(h,a)].append((m, loc.date().isoformat()))
        except (KeyError, ValueError, TypeError):
            continue
    issues=[]
    used_ids=set()
    for row in rows:
        key=(canonical(row["home"]),canonical(row["away"]))
        found=indexes.get(key,[])
        issue={"id":row["id"],"home":row["home"],"away":row["away"],
               "sourceDate":row["date"],"cc0Date":row.get("cc0Date"),
               "dateDisagreement":bool(row.get("dateDisagreement",False)),
               "timeVerifiedUTC":None}
        if len(found)!=1:
            issue["status"]="UNMATCHED_OR_AMBIGUOUS";issues.append(issue);continue
        match,local_date=found[0]
        fid=match.get("id")
        if fid is None or fid in used_ids:
            issue["status"]="DUPLICATE_OR_MISSING_PROVIDER_ID";issues.append(issue);continue
        used_ids.add(fid)
        issue.update({"footballDataId":fid,"footballDataUtc":match["utcDate"],
                      "footballDataLondonDate":local_date})
        if local_date==row["date"]:
            issue["status"]="STAGING_DATE_CORROBORATED"
        elif row.get("cc0Date") and local_date==row.get("cc0Date"):
            issue["status"]="REFERENCE_DATE_CORROBORATED"
        else:
            issue["status"]="THIRD_SOURCE_DATE_DISAGREEMENT"
        # Never promote a single source's kickoff to a confirmed multi-source clock time.
        issues.append(issue)
    counts=dict(Counter(r["status"] for r in issues))
    return {"season":"2026-27","scope":"EPL third-source date checks, staging-only",
            "source":"football-data.org /v4/competitions/PL/matches?season=2026",
            "clockPolicy":"UTC timestamp is one-provider observation, not verified two-source hour gap",
            "coverage":counts,"total":len(issues),
            "dateDisagreements":sum(x["dateDisagreement"] for x in issues),
            "issues":issues}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=STAGE)
    p.add_argument("--api-json",type=Path)
    p.add_argument("--out",type=Path,default=OUTPUT)
    a=p.parse_args()
    stage=json.loads(a.input.read_text(encoding="utf-8"))
    if a.api_json:
        payload=json.loads(a.api_json.read_text(encoding="utf-8"))
    else:
        token=os.environ.get("FOOTBALL_DATA_TOKEN")
        if not token:raise RuntimeError("FOOTBALL_DATA_TOKEN is required")
        r=requests.get("https://api.football-data.org/v4/competitions/PL/matches?season=2026",
                       headers={"X-Auth-Token":token},timeout=35)
        r.raise_for_status()
        payload=r.json()
    report=reconcile(stage,payload)
    if report["total"]!=380:
        raise ValueError("Incomplete EPL source staging")
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("Third-source EPL date reconciliation:",report["coverage"],
          "conflicts:",report["dateDisagreements"])

if __name__=="__main__":
    main()
