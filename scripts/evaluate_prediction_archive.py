#!/usr/bin/env python3
"""Evaluate frozen pre-kickoff EPL three-way probabilities against final results.

Uses archived predictions, NOT predictions regenerated after a fixture.
This produces a non-commercial internal report only; it does not modify
the forecast model or claim data-feed commercial rights.
"""
import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/data/match_archive.json"
JSON_OUT = ROOT / "data/performance/epl_prediction_accuracy.json"
MD_OUT = ROOT / "data/performance/EPL_PREDICTION_ACCURACY_KO.md"
OUTCOMES = ("home","draw","away")

def timestamp(s):
    return datetime.fromisoformat(s.replace("Z","+00:00"))

def classify(record):
    if record.get("status")!="FINISHED":
        return None,"not_finished"
    snap=record.get("snapshot")
    result=record.get("result")
    if not isinstance(snap,dict) or not isinstance(result,dict):
        return None,"missing_snapshot_or_result"
    try:
        before=timestamp(snap["capturedAt"])
        kickoff=timestamp(snap["utcDate"])
    except (KeyError,TypeError,ValueError):
        return None,"invalid_capture_or_kickoff"
    if before.tzinfo is None or kickoff.tzinfo is None or before >= kickoff:
        return None,"not_frozen_before_kickoff"
    try:
        probs=[float(snap[k]) for k in ("homeWin","draw","awayWin")]
        hg,ag=result["homeGoals"],result["awayGoals"]
    except (KeyError,TypeError,ValueError):
        return None,"missing_probabilities_or_scores"
    if any(not math.isfinite(p) or p<=0 or p>=1 for p in probs):
        return None,"invalid_probabilities"
    if abs(sum(probs)-1)>1e-4:
        return None,"not_normalized"
    if type(hg) is not int or type(ag) is not int or min(hg,ag)<0:
        return None,"invalid_final_score"
    if not isinstance(snap.get("home"),str) or not isinstance(snap.get("away"),str):
        return None,"missing_team"
    if not snap["home"].strip() or not snap["away"].strip() or snap["home"]==snap["away"]:
        return None,"invalid_team"
    actual=0 if hg>ag else 1 if hg==ag else 2
    predicted=max(range(3),key=lambda i:probs[i])
    return {
        "utcDate":snap["utcDate"],"date":snap.get("date") or kickoff.date().isoformat(),
        "home":snap["home"],"away":snap["away"],
        "homeGoals":hg,"awayGoals":ag,
        "probabilities":{"home":probs[0],"draw":probs[1],"away":probs[2]},
        "actualOutcome":OUTCOMES[actual],"mostLikelyOutcome":OUTCOMES[predicted],
        "correctTop1":int(predicted==actual),
        "brier":sum((p-int(i==actual))**2 for i,p in enumerate(probs)),
        "logLoss":-math.log(probs[actual]),
        "homeExpectedPoints":3*probs[0]+probs[1],
        "awayExpectedPoints":3*probs[2]+probs[1],
        "capturedAt":snap["capturedAt"]
    },None

def evaluate(archive):
    archive_matches=archive.get("matches",{})
    if not isinstance(archive_matches,dict):
        raise ValueError("Archive matches must be a fixture-ID map")
    valid=[]
    rejected=Counter()
    for fixture_id,record in archive_matches.items():
        classified,reason=classify(record)
        if reason:
            rejected[reason]+=1
        else:
            classified["fixtureId"]=str(fixture_id)
            valid.append(classified)
    valid.sort(key=lambda x:(x["utcDate"],x["fixtureId"]))
    if not valid:
        raise ValueError("No eligible pre-kickoff snapshot with final result")
    n=len(valid)
    top1=sum(x["correctTop1"] for x in valid)
    result_counts=Counter(x["actualOutcome"] for x in valid)
    teams=defaultdict(lambda:{"matches":0,"expectedPoints":0.0,"actualPoints":0})
    for row in valid:
        h=teams[row["home"]]
        a=teams[row["away"]]
        h["matches"]+=1
        a["matches"]+=1
        h["expectedPoints"]+=row["homeExpectedPoints"]
        a["expectedPoints"]+=row["awayExpectedPoints"]
        actual=row["actualOutcome"]
        h["actualPoints"]+=3 if actual=="home" else 1 if actual=="draw" else 0
        a["actualPoints"]+=3 if actual=="away" else 1 if actual=="draw" else 0
    team_records=[]
    for name,s in teams.items():
        team_records.append({
            "team":name,"matches":s["matches"],
            "expectedPoints":round(s["expectedPoints"],3),
            "actualPoints":s["actualPoints"],
            "pointsAboveExpected":round(s["actualPoints"]-s["expectedPoints"],3),
            "perMatchDifference":round((s["actualPoints"]-s["expectedPoints"])/s["matches"],3)
        })
    team_records.sort(key=lambda x:(-x["pointsAboveExpected"],x["team"]))
    all_ex=sum(s["expectedPoints"] for s in teams.values())
    all_actual=sum(s["actualPoints"] for s in teams.values())
    return {
        "schemaVersion":1,"source":"docs/data/match_archive.json",
        "method":"Frozen pre-kickoff probabilities only; three-class 90-minute results",
        "sample":{"archivedFixtures":len(archive_matches),
                  "eligibleFinalizedFixtures":n,
                  "excludedReasons":dict(rejected),
                  "firstFixtureDate":valid[0]["date"],
                  "lastFixtureDate":valid[-1]["date"],
                  "uniqueTeams":len(team_records),
                  "teamAppearances":sum(x["matches"] for x in team_records)},
        "results":{
            "top1Correct":top1,
            "top1Accuracy":round(top1/n,6),
            "multiclassBrierSum":round(sum(x["brier"] for x in valid)/n,6),
            "logLoss":round(sum(x["logLoss"] for x in valid)/n,6),
            "outcomeCounts":{k:result_counts[k] for k in OUTCOMES},
            "uniformOneThirdBrier":round(2/3,6),
            "uniformOneThirdLogLoss":round(math.log(3),6),
            "alwaysPredictHomeAccuracyOnSample":round(result_counts["home"]/n,6),
            "sumExpectedPointsForBothTeams":round(all_ex,3),
            "sumActualPointsForBothTeams":all_actual,
        },
        "teamRecords":team_records,
        "fixtures":[
            {**row,"brier":round(row["brier"],6),"logLoss":round(row["logLoss"],6),
             "homeExpectedPoints":round(row["homeExpectedPoints"],3),
             "awayExpectedPoints":round(row["awayExpectedPoints"],3)}
            for row in valid
        ],
        "interpretationLimits":[
            "Only archived 40 results available as of this run; a small sample is not proof of predictive superiority.",
            "Top-1 accuracy ignores probability calibration and should be shown with Brier and Log Loss.",
            "All three probabilities are evaluated, with Brier defined as the sum of 3 squared class errors (not divided by 3).",
            "Team points-above-expected over four matches is not a reliable causal measure of strength or coaching.",
            "Any future rescheduled fixtures are excluded if capture time is not before recorded kickoff.",
            "GOAL API archived match results are not independently audited here; external data licensing remains separate."
        ]
    }

def write_report(report, output_path=MD_OUT):
    output_path=Path(output_path)
    r=report["results"]
    s=report["sample"]
    text=[
        "# EPL Run-in Lab — 과거 예측 성능 검증",
        "",
        f'평가 기간: {s["firstFixtureDate"]}~{s["lastFixtureDate"]}',
        "",
        f'- 경기 전 예측+실제 종료 결과: **{s["eligibleFinalizedFixtures"]}경기**',
        f'- 최다 확률 결과 적중: **{r["top1Correct"]}/{s["eligibleFinalizedFixtures"]}경기 ({100*r["top1Accuracy"]:.1f}%)**',
        f'- 다중분류 Brier Score (3개 항 합): **{r["multiclassBrierSum"]:.4f}** (동일확률 기준 {r["uniformOneThirdBrier"]:.4f})',
        f'- Log Loss: **{r["logLoss"]:.4f}** (동일확률 기준 {r["uniformOneThirdLogLoss"]:.4f})',
        f'- 동일 표본에서 단순 홈승 선택 적중률: **{100*r["alwaysPredictHomeAccuracyOnSample"]:.1f}%**',
        "",
        "## 구단별 예상 승점과 실제 승점",
        "",
        "| 구단 | 경기 | 예상 승점 | 실제 승점 | 실제 - 예상 |",
        "|---|---:|---:|---:|---:|"
    ]
    for t in report["teamRecords"]:
        text.append(f'| {t["team"]} | {t["matches"]} | {t["expectedPoints"]:.2f} | '
                    f'{t["actualPoints"]} | {t["pointsAboveExpected"]:+.2f} |')
    text += [
        "",
        "## 해석 주의",
        "",
        "- 저장 시각이 킥오프보다 빠른, 실제 종료 결과가 연결된 경기만 분석.",
        "- Brier Score와 Log Loss는 작을수록 좋다. 모델이 우월하다는 통계적 검증은 아직 아님.",
        "- 구단별 표본이 적고 상대 난이도가 달라 승점 차이를 팀 실력의 증명으로 사용하지 않는다.",
        "- 데이터 공급자 이용 권한 및 상업적 재사용은 별도 확인 필요; 현재 모델 코드와 데이터 소스를 변경하지 않았다.",
        ""
    ]
    output_path.parent.mkdir(parents=True,exist_ok=True)
    output_path.write_text("\n".join(text),encoding="utf-8")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--archive",type=Path,default=SOURCE)
    p.add_argument("--out",type=Path,default=JSON_OUT)
    p.add_argument("--md",type=Path,default=MD_OUT)
    a=p.parse_args()
    archive=json.loads(a.archive.read_text(encoding="utf-8"))
    report=evaluate(archive)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    write_report(report,a.md)
    print("Pre-match accuracy report:",report["sample"],report["results"])

if __name__=="__main__":
    main()
